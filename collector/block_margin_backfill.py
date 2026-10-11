#!/usr/bin/env python3
"""Backfill collectors for ② block trades and ③ margin (official sources).

Modes:
  python block_margin_backfill.py block  sse  [--dates ...]   # 大宗 SSE
  python block_margin_backfill.py block  szse                 # 大宗 SZSE
  python block_margin_backfill.py margin sse                  # 两融 SSE
  python block_margin_backfill.py margin szse                 # 两融 SZSE

Same resume/state/raw-append-only conventions as lhb_backfill.py.
SZSE modes refuse to run while another SZSE collector holds the lock
(lhb/.backfill.lock or blockmargin lock) — see LHB_PIPELINE.md lesson.
"""
from __future__ import annotations
import argparse
import json
import random
import re
import sys
import time
import os
import msvcrt
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from net_common import ThrottledClient, qs  # noqa: E402

NODE = Path(r'D:\tdx-node')
ROOT = NODE / 'blockmargin'
RAW = ROOT / 'raw'
STATE_FP = ROOT / 'backfill_state.json'
CAL_FP = NODE / 'manifests' / 'trading_calendar_2021_2026.json'
PREFILL_FP = NODE / 'manifests' / 'calendar_prefill_2021.json'
LOCK_FP = ROOT / '.bm_backfill.lock'

SSE_HEADERS = {'Referer': 'http://www.sse.com.cn/'}
SZSE_HEADERS = {'Referer': 'https://www.szse.cn/'}
SZSE_API = 'https://www.szse.cn/api/report/ShowReport/data'

sse_cli = ThrottledClient(min_interval_s=0.22)
szse_cli = ThrottledClient(min_interval_s=0.35, max_retries=8,
                            breaker_threshold=3, cooldown_s=150.0)


def load_calendar() -> list[str]:
    days = set()
    if CAL_FP.exists():
        days.update(json.loads(CAL_FP.read_text(encoding='utf-8')))
    if PREFILL_FP.exists():
        days.update(json.loads(PREFILL_FP.read_text(encoding='utf-8')))
    return sorted(days)


def load_state() -> dict:
    if STATE_FP.exists():
        return json.loads(STATE_FP.read_text(encoding='utf-8'))
    return {}


def save_state(state: dict):
    # Multiple SSE workers (block + margin) share this state file. Serialize
    # the read/merge/replace transaction across processes to avoid Windows
    # PermissionError/last-writer races.
    lock_fp = ROOT / '.state.lock'
    lock_fp.parent.mkdir(parents=True, exist_ok=True)
    with lock_fp.open('a+b') as lockf:
        lockf.seek(0, os.SEEK_END)
        if lockf.tell() == 0:
            lockf.write(b'0')
            lockf.flush()
        while True:
            try:
                lockf.seek(0)
                msvcrt.locking(lockf.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                time.sleep(0.05)
        try:
            merged: dict = {}
            try:
                if STATE_FP.exists():
                    merged.update(json.loads(STATE_FP.read_text(encoding='utf-8')))
            except (json.JSONDecodeError, OSError):
                pass
            merged.update(state)
            tmp = ROOT / f'.backfill_state.{os.getpid()}.{random.randrange(1<<30)}.tmp'
            tmp.write_text(json.dumps(merged, ensure_ascii=False, indent=1),
                           encoding='utf-8')
            # Windows may briefly deny replace if another process has the file
            # open; retry while holding the cross-process state lock.
            for attempt in range(12):
                try:
                    tmp.replace(STATE_FP)
                    break
                except PermissionError:
                    if attempt == 11:
                        raise
                    time.sleep(0.1 * (attempt + 1))
            state.clear()
            state.update(merged)
        finally:
            lockf.seek(0)
            msvcrt.locking(lockf.fileno(), msvcrt.LK_UNLCK, 1)


def save_raw(rel: str, obj) -> None:
    fp = RAW / rel
    fp.parent.mkdir(parents=True, exist_ok=True)
    if not fp.exists():
        fp.write_text(json.dumps(obj, ensure_ascii=False), encoding='utf-8')


def szse_lock_held_by_other() -> bool:
    """True if any SZSE-consuming collector (LHB or this one) is running."""
    for lk in (NODE / 'lhb' / '.backfill.lock', LOCK_FP):
        if lk.exists():
            try:
                import ctypes
                pid = int(lk.read_text().strip())
                h = ctypes.windll.kernel32.OpenProcess(0x00100000, False, pid)
                if h:
                    ctypes.windll.kernel32.CloseHandle(h)
                    return True
            except (ValueError, OSError, AttributeError):
                pass
    return False


# ------------------------------------------------------------ xlsx fast path
# SZSE ShowReport metadata advertises "excel":"xlsx". If the probe found a
# working export variant AND we have a header->field translation for the
# sheet, per-day fetch collapses from N pages to one file. Any failure
# falls back to the proven JSON pagination path permanently for the run.
XLSX_PROBE_FP = ROOT / 'xlsx_probe.json'
XLSX_STATE = {'usable': None}


def xlsx_url_params(catalog: str, tab: str, extra: dict):
    if not XLSX_PROBE_FP.exists():
        return None
    probe = json.loads(XLSX_PROBE_FP.read_text(encoding='utf-8'))
    if catalog == '1837_xxpl':
        candidates = [r for r in probe if not r.get('name', '').startswith('block')]
    elif catalog == '1932_dzjyzqjy_after':
        candidates = [r for r in probe if r.get('name', '').startswith('block1932')]
    elif catalog == '1265':
        candidates = [r for r in probe if r.get('name', '').startswith('block1265')]
    else:
        candidates = probe
    winner = next((r for r in candidates if r.get('xlsx')), None)
    if not winner:
        return None
    path = 'data' if winner['name'].startswith('data') else 'export'
    showtype = 'XLSX' if 'SHOWTYPE=XLSX' in winner['name'] else 'EXCEL'
    params = {'SHOWTYPE': showtype, 'CATALOGID': catalog, 'TABKEY': tab,
              'random': f'{random.random():.6f}'}
    params.update(extra)
    return ('https://www.szse.cn/api/report/ShowReport/' + path + '?' +
            qs(params))


def fetch_xlsx_rows(url: str) -> list[dict]:
    """Download xlsx and return rows as dicts keyed by header text."""
    raw = szse_cli.get_bytes(url, extra_headers=SZSE_HEADERS)
    import io
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True)
    ws = wb.active
    it = ws.iter_rows(values_only=True)
    header = None
    out = []
    for row in it:
        vals = ['' if c is None else str(c).strip() for c in row]
        if header is None:
            if any(vals):
                header = vals
            continue
        if any(vals):
            out.append(dict(zip(header, vals)))
    return out


# ------------------------------------------------------------ block / sse
def day_block_sse(day: str) -> list[dict]:
    iso = f'{day[:4]}-{day[4:6]}-{day[6:]}'
    rows: list[dict] = []
    page = 1
    while True:
        params = {'isPagination': 'true', 'pageHelp.pageSize': '1000',
                  'pageHelp.pageNo': str(page), 'pageHelp.beginPage': str(page),
                  'pageHelp.cacheSize': '1', 'pageHelp.endPage': str(page),
                  'sqlId': 'COMMON_SSE_XXPL_JYXXPL_DZJYXX_L_1',
                  'stockId': '', 'startDate': iso, 'endDate': iso}
        obj = sse_cli.get_json(
            'http://query.sse.com.cn/commonQuery.do?' + qs(params),
            extra_headers={'Referer': 'http://www.sse.com.cn/disclosure/'
                                      'diclosure/block/deal/dzjyxx/'})
        save_raw(f'block/sse/{day}_p{page}.json', obj)
        ph = obj.get('pageHelp') or {}
        page_rows = ph.get('data') or []
        rows.extend(page_rows)
        total = ph.get('total') or 0
        if not page_rows or len(rows) >= total:
            break
        page += 1
    return rows


# ------------------------------------------------------------ block / szse
BLOCK_BZ_RE = re.compile(r'txtkey2=(\d+)&txtKsrq=([\d-]+)&txtZzrq=([\d-]+)')


def day_block_szse(day: str) -> tuple[int, int]:
    iso = f'{day[:4]}-{day[4:6]}-{day[6:]}'
    rows: list[dict] = []
    pageno, pagecount = 1, 1
    while pageno <= pagecount:
        obj = szse_cli.get_json(SZSE_API + '?' + qs({
            'SHOWTYPE': 'JSON', 'CATALOGID': '1932_dzjyzqjy_after',
            'TABKEY': 'tab1', 'txtStart': iso, 'txtEnd': iso,
            'PAGENO': str(pageno), 'random': f'{random.random():.6f}',
        }), extra_headers=SZSE_HEADERS)
        save_raw(f'block/szse_list/{day}_p{pageno}.json', obj)
        md = obj[0]['metadata']
        pagecount = int(md.get('pagecount') or 1)
        rows.extend(obj[0].get('data') or [])
        pageno += 1
    n_detail = 0
    for r in rows:
        m = BLOCK_BZ_RE.search(r.get('bz') or '')
        if not m:
            continue
        code, ksrq, zzrq = m.groups()
        obj = szse_cli.get_json(SZSE_API + '?' + qs({
            'SHOWTYPE': 'JSON', 'CATALOGID': '1265', 'TABKEY': 'tab1',
            'txtkey2': code, 'txtKsrq': ksrq, 'txtZzrq': zzrq,
            'random': f'{random.random():.6f}',
        }), extra_headers=SZSE_HEADERS)
        save_raw(f'block/szse_detail/{day}_{code}.json', obj)
        n_detail += 1
    return len(rows), n_detail


# ------------------------------------------------------------ margin / sse
def day_margin_sse(day: str) -> list[dict]:
    rows: list[dict] = []
    page = 1
    while True:
        params = {'isPagination': 'true', 'pageHelp.pageSize': '3000',
                  'pageHelp.pageNo': str(page), 'pageHelp.beginPage': str(page),
                  'pageHelp.cacheSize': '1', 'pageHelp.endPage': str(page),
                  'sqlId': 'RZRQ_MX_INFO', 'beginDate': day, 'endDate': day}
        obj = sse_cli.get_json(
            'http://query.sse.com.cn/commonSoaQuery.do?' + qs(params),
            extra_headers={'Referer': 'http://www.sse.com.cn/market/'
                                      'othersdata/margin/detail/'})
        save_raw(f'margin/sse/{day}_p{page}.json', obj)
        ph = obj.get('pageHelp') or {}
        page_rows = ph.get('data') or []
        rows.extend(page_rows)
        total = ph.get('total') or 0
        if not page_rows or len(rows) >= total:
            break
        page += 1
    return rows


# ------------------------------------------------------------ margin / szse
def day_margin_szse(day: str) -> int:
    iso = f'{day[:4]}-{day[4:6]}-{day[6:]}'
    # fast path: one xlsx per day (only when probe found a working variant
    # AND a header translation is configured; falls back permanently on
    # any failure)
    if XLSX_STATE['usable'] is not False:
        url = None
        try:
            url = xlsx_url_params('1837_xxpl', 'tab2', {'txtDate': iso})
        except (OSError, json.JSONDecodeError):
            pass
        if url:
            try:
                raw_rows = fetch_xlsx_rows(url)
                save_raw(f'margin/szse_xlsx/{day}.json',
                         {'sheet_rows': raw_rows})
                return len(raw_rows)
            except Exception as exc:  # noqa: BLE001
                print(f'  xlsx path failed ({exc!r}); JSON fallback',
                      flush=True)
                XLSX_STATE['usable'] = False
    rows = 0
    pageno, pagecount = 1, 1
    while pageno <= pagecount:
        obj = szse_cli.get_json(SZSE_API + '?' + qs({
            'SHOWTYPE': 'JSON', 'CATALOGID': '1837_xxpl', 'TABKEY': 'tab2',
            'txtDate': iso, 'PAGENO': str(pageno),
            'random': f'{random.random():.6f}',
        }), extra_headers=SZSE_HEADERS)
        save_raw(f'margin/szse/{day}_p{pageno}.json', obj)
        md = obj[0]['metadata']
        pagecount = int(md.get('pagecount') or 1)
        rows += len(obj[0].get('data') or [])
        pageno += 1
    return rows


# ------------------------------------------------------------ orchestrate
def process_day(kind: str, exch: str, day: str, state: dict):
    t0 = time.time()
    if kind == 'block' and exch == 'sse':
        rows = day_block_sse(day)
        rec = {'rows': len(rows)}
    elif kind == 'block' and exch == 'szse':
        n_list, n_detail = day_block_szse(day)
        rec = {'list_rows': n_list, 'details': n_detail}
    elif kind == 'margin' and exch == 'sse':
        rows = day_margin_sse(day)
        rec = {'rows': len(rows)}
    else:
        rows_n = day_margin_szse(day)
        rec = {'rows': rows_n}
    rec.update({
        'status': 'COMPLETE',
        'secs': round(time.time() - t0, 1),
        'retrieved_at': datetime.now(timezone.utc).isoformat(),
        'source': f'{exch.upper()} official ({kind})',
    })
    state[f'{kind}/{exch}/{day}'] = rec
    save_state(state)
    print(f'[{day}] {kind}/{exch} {rec} ', flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('kind', choices=['block', 'margin'])
    ap.add_argument('exchange', choices=['sse', 'szse'])
    ap.add_argument('--dates')
    ap.add_argument('--from', dest='from_')
    ap.add_argument('--to', dest='to_')
    args = ap.parse_args()

    ROOT.mkdir(exist_ok=True)
    RAW.mkdir(exist_ok=True)

    if args.exchange == 'szse':
        if szse_lock_held_by_other():
            print('another SZSE collector is running — aborting '
                  '(see LHB_PIPELINE.md concurrency lesson)', flush=True)
            return 2
        LOCK_FP.write_text(str(__import__('os').getpid()))

    state = load_state()
    if args.dates:
        days = [d.strip() for d in args.dates.split(',') if d.strip()]
    else:
        cal = load_calendar()
        lo = args.from_ or '20210101'
        hi = args.to_ or datetime.now().strftime('%Y%m%d')
        days = [d for d in cal if lo <= d <= hi]
    prefix = f'{args.kind}/{args.exchange}/'
    # SZSE margin publishes T+1 morning: a zero-row COMPLETE inside the last
    # 7 days is a publication-window artifact, not a real holiday/empty day —
    # keep it retryable. Older zero-row days stay COMPLETE (idempotent backfill).
    retry_cutoff = (datetime.now() - timedelta(days=7)).strftime('%Y%m%d')

    def _needs(d: str) -> bool:
        rec = state.get(prefix + d, {})
        if rec.get('status') != 'COMPLETE':
            return True
        return (prefix == 'margin/szse/' and rec.get('rows') == 0
                and d >= retry_cutoff)

    todo = [d for d in days if _needs(d)]
    print(f'{len(days)} days, {len(todo)} to do ({prefix})', flush=True)
    for i, day in enumerate(todo, 1):
        try:
            process_day(args.kind, args.exchange, day, state)
        except RuntimeError as exc:
            state[prefix + day] = {'status': 'FAILED', 'error': str(exc)[:400]}
            save_state(state)
            print(f'[{day}] FAILED: {exc}', flush=True)
        if i % 100 == 0:
            print(f'-- {i}/{len(todo)}', flush=True)
    done = sum(1 for d in todo
               if state.get(prefix + d, {}).get('status') == 'COMPLETE')
    print(f'FINISHED {done}/{len(todo)}', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
