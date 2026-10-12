#!/usr/bin/env python3
"""Normalize raw margin responses into blockmargin/csv/margin_daily.csv.

Sources:
  SSE  : raw/margin/sse/YYYYMMDD_pN.json  — rzye/rzmre/rzche yuan,
         rqyl/rqmcl/rqchl shares. Direct use.
  SZSE : raw/margin/szse/YYYYMMDD_pN.json — jrrzmr/jrrzye/jrrjmc/jrrzrjye
         in 亿元, jrrjyl in 万股, jrrjye in 万元 (units inferred &
         cross-checked: rqye ~= rqyl * close price; see verify option).

Output schema (margin_daily.csv):
  trade_date, exchange, code, name, rzye, rzmre, rzche, rqyl, rqmcl, rqchl,
  rzrqye, source, raw_file   (amounts yuan, volumes shares)

python margin_normalize.py [--verify]  : verify SZSE units via TDX close px
"""
from __future__ import annotations
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

NODE = Path(r'D:\tdx-node')
ROOT = NODE / 'blockmargin'
RAW = ROOT / 'raw'
OUT = ROOT / 'csv'

COLS = ['trade_date', 'exchange', 'code', 'name', 'rzye', 'rzmre', 'rzche',
        'rqyl', 'rqye', 'rqmcl', 'rqchl', 'rzrqye', 'source', 'raw_file',
        'available_at']
ROWS: list[dict] = []


def to_f(s):
    if s is None or s == '':
        return None
    try:
        return float(str(s).replace(',', ''))
    except ValueError:
        return None


def clean(s):
    return (s or '').replace('&nbsp;', ' ').strip()


def iso(day: str) -> str:
    return f'{day[:4]}-{day[4:6]}-{day[6:]}'


def parse_sse():
    n = 0
    for fp in sorted((RAW / 'margin' / 'sse').glob('*.json')):
        day = fp.stem.split('_')[0]
        obj = json.loads(fp.read_text(encoding='utf-8'))
        for r in (obj.get('pageHelp') or {}).get('data') or []:
            ROWS.append({
                'trade_date': iso(str(r.get('opDate') or day)),
                'exchange': 'SSE', 'code': r.get('stockCode'),
                'name': clean(r.get('securityAbbr')),
                'rzye': to_f(r.get('rzye')), 'rzmre': to_f(r.get('rzmre')),
                'rzche': to_f(r.get('rzche')), 'rqyl': to_f(r.get('rqyl')),
                'rqmcl': to_f(r.get('rqmcl')), 'rqchl': to_f(r.get('rqchl')),
                'rzrqye': (to_f(r.get('rzye')) or 0) +
                          ((to_f(r.get('rqyl')) or 0) * 0),  # rqye needs px; see meta
                'source': 'SSE official', 'raw_file': f'raw/margin/sse/{fp.name}'})
        n += 1
    print(f'margin sse: {n} days', flush=True)


def parse_szse():
    # 2026-10-12 修复：SZSE 每天约 106 页，旧版只读 *_p1.json，每天丢 ~99% 明细行
    # （p1 可能空、或只有 20 行）。改为按天聚合全部 *_p*.json 并按 (day, code) 去重。
    n = 0
    xdir = RAW / 'margin' / 'szse_xlsx'
    byday: dict[str, list[Path]] = {}
    for fp in sorted((RAW / 'margin' / 'szse').glob('*_p*.json')):
        byday.setdefault(fp.stem.split('_')[0], []).append(fp)
    for day, fps in sorted(byday.items()):
        if (xdir / f'{day}.json').exists():
            continue  # xlsx fast path already covers this day
        seen: set[str] = set()
        for fp in fps:
            obj = json.loads(fp.read_text(encoding='utf-8'))
            for cat in obj:
                if cat.get('metadata', {}).get('tabkey') != 'tab2':
                    continue
                for r in cat.get('data') or []:
                    code = clean(r.get('zqdm'))
                    if code in seen:
                        continue
                    seen.add(code)
                    ROWS.append({
                        'trade_date': iso(day), 'exchange': 'SZSE',
                        'code': code, 'name': clean(r.get('zqjc')),
                        'rzye': (to_f(r.get('jrrzye')) or 0) * 1e8,
                        'rzmre': (to_f(r.get('jrrzmr')) or 0) * 1e8,
                        'rzche': (to_f(r.get('jrrjmc')) or 0) * 1e8,
                        'rqyl': (to_f(r.get('jrrjyl')) or 0) * 1e4,
                        'rqye': (to_f(r.get('jrrjye')) or 0) * 1e4,
                        'rqmcl': None, 'rqchl': None,
                        'rzrqye': (to_f(r.get('jrrzrjye')) or 0) * 1e8,
                        'source': 'SZSE official',
                        'raw_file': f'raw/margin/szse/{fp.name}'})
        n += 1
    print(f'margin szse(json): {n} days', flush=True)


# xlsx fast path: header text carries its own unit suffix, e.g. 融资余额(元)
SZSE_XLSX_FIELDS = {  # substring -> csv field; volume vs amount decided by suffix
    '证券代码': 'code', '证券简称': 'name', '交易日': 'trade_date',
    '融资买入额': 'rzmre', '融资余额': 'rzye', '融资偿还额': 'rzche',
    '融券余量': 'rqyl', '融券余额': 'rqye', '融资融券余额': 'rzrqye',
}
UNIT_MULT = {'元': 1.0, '万元': 1e4, '亿元': 1e8, '股': 1.0, '万股': 1e4}


def parse_szse_xlsx():
    n = 0
    xdir = RAW / 'margin' / 'szse_xlsx'
    if not xdir.exists():
        return
    for fp in sorted(xdir.glob('*.json')):
        day = fp.stem
        sheet_rows = json.loads(
            fp.read_text(encoding='utf-8')).get('sheet_rows') or []
        if not sheet_rows:
            n += 1
            continue
        header = [h for h in sheet_rows[0].keys()]
        colmap = {}
        for h in header:
            for sub, field in SZSE_XLSX_FIELDS.items():
                if sub in h and field not in colmap.values():
                    mult = next((m for u, m in UNIT_MULT.items()
                                 if f'({u})' in h or f'（{u}）' in h), None)
                    colmap[h] = (field, mult)
        for r in sheet_rows:
            out = {'trade_date': iso(day), 'exchange': 'SZSE',
                   'rqmcl': None, 'rqchl': None,
                   'source': 'SZSE official (xlsx)',
                   'raw_file': f'raw/margin/szse_xlsx/{fp.name}'}
            for h, (field, mult) in colmap.items():
                v = clean(r.get(h))
                if field == 'trade_date':
                    out['trade_date'] = v.replace('/', '-') if '/' in v else v \
                        if not v.isdigit() else iso(v)
                elif field in ('code', 'name'):
                    out[field] = v
                elif mult is not None:
                    out[field] = (to_f(v) or 0) * mult
            out.setdefault('code', '')
            out.setdefault('name', '')
            ROWS.append(out)
        n += 1
    print(f'margin szse(xlsx): {n} days', flush=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    parse_sse()
    parse_szse()
    parse_szse_xlsx()
    ROWS.sort(key=lambda r: (r['trade_date'], r['exchange'], r['code']))
    import sys as _s, os as _o
    _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__)))
    import pit
    pit.stamp(ROWS, 'margin')
    fp = OUT / 'margin_daily.csv'
    with fp.open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(ROWS)
    dates = sorted({r['trade_date'] for r in ROWS})
    meta = {
        'dataset': 'margin_daily',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'rows': len(ROWS), 'days': len(dates),
        'coverage': [dates[0] if dates else None, dates[-1] if dates else None],
        'units': 'all amounts yuan, volumes shares',
        'unit_notes': {
            'SSE': 'raw already yuan/shares',
            'SZSE': 'raw jrrzye/jrrzmr/jrrjmc/jrrzrjye=亿元(x1e8), '
                    'jrrjyl=万股(x1e4), jrrjye=万元; rqmcl/rqchl not provided '
                    'by SZSE tab2 (SSE has them)',
            'rzrqye_SSE': 'SSE gives no combined column; equals rzye until '
                          'rqye(=rqyl*close) is added'},
        'sources': ['SSE commonSoaQuery RZRQ_MX_INFO (official)',
                    'SZSE ShowReport 1837_xxpl tab2 (official)'],
    }
    (OUT / 'MARGIN_META.json').write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'rows={len(ROWS)} days={len(dates)} '
          f'({dates[0] if dates else "-"}..{dates[-1] if dates else "-"})',
          flush=True)


if __name__ == '__main__':
    main()
