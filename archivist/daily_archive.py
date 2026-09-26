#!/usr/bin/env python3
"""Task 3: TDX daily archivist — forward-PIT snapshot archive (free-account sources only).

AUDIT-FIX2 (2026-09-26, second external audit of 1576e02) — freezes the
completeness contract so COMPLETE means "everything the day owed us":
  1. universe is HARD-FROZEN at 84 codes (baseline 1cabde8). A missing,
     corrupt or renamed csr84_universe.json is a fatal FAILED — the expected
     request set can never silently shrink. universe_sha256 is recorded.
  2. gb_today_watchlist is ONE grouped mandatory request (audit option B):
     its internal n_nonempty/n_empty/n_failed tally must sum to
     universe_size. Request cardinality == completeness cardinality.
  3. expected contract is frozen and asserted:
       regular day  = 4 markets + 8 PCF + 1 gb group + 20 LHB + 20 unlock = 53
       holders day  = 53 + 84 holders = 137  (Monday, or --force)
     a mismatch is a fatal FAILED (code bug, not data condition).
  4. directory invariant: actual files == manifest-declared files
     (orphan_files == 0 and missing_files == 0), else the day is PARTIAL.
     --force first clears the day directory so reruns cannot leak orphans.
  5. day status COMPLETE / PARTIAL / FAILED with frozen counters
     (expected/successful/nonempty/empty/failed/sha_verified/sha_failures,
      files_declared/present/orphan/missing) and per-request outcomes
     SUCCESS_NONEMPTY / SUCCESS_EMPTY / FAILED.

Sources captured (free account only): ETF list (31), CSI300 (23), margin
categories 56/57, ETF watchlist PCF (type 2), CSR-84 same-day share snapshot,
watchlist LHB (6) / unlock (7), weekly holders (1).

Red lines honored: ETF get_gb_info_by_date is NEVER used (false history);
no credentials are read — the client's own auto-login is the only auth.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import socket
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

NODE_ROOT = Path(r'D:\tdx-node')
CLIENT_DIR = NODE_ROOT / 'tdx-tq-v773'
USER_DIR = CLIENT_DIR / 'PYPlugins' / 'user'
DATA_DIR = CLIENT_DIR / 'PYPlugins' / 'data'
TDX_EXE = CLIENT_DIR / 'TdxW.exe'
ARCHIVE_ROOT = NODE_ROOT / 'archive'
UNIVERSE_FILE = NODE_ROOT / 'manifests' / 'csr84_universe.json'

UNIVERSE_FROZEN_SIZE = 84
UNIVERSE_BASELINE_COMMIT = '1cabde8'
LHB_UNLOCK_WINDOW = 20

sys.path.insert(0, str(USER_DIR))
from tqcenter import tq  # noqa: E402

ETF_WATCHLIST = [
    '510300.SH', '510050.SH', '159919.SZ', '159915.SZ',
    '512880.SH', '518880.SH', '513050.SH', '512100.SH',
]
MARKET_SNAPSHOTS = {'31': 'etf_list', '23': 'csi300', '56': 'margin_cat56', '57': 'margin_cat57'}

FILE_PREFIX = {'lhb': 'lhb', 'unlock': 'lockshare'}

NONEMPTY, EMPTY, FAILED = 'SUCCESS_NONEMPTY', 'SUCCESS_EMPTY', 'FAILED'


def src_name(kind: str, num: str, down_time: str) -> str:
    """Exact client-side file name for each download_file kind."""
    if kind == 'pcf':
        return f'etfpcf{num}_{down_time}.json'
    if kind == 'holders':
        return f'holders{num}_{down_time[:4]}.json'
    return f'{FILE_PREFIX[kind]}{num}.json'


class Counters:
    def __init__(self):
        self.expected = 0
        self.nonempty = 0
        self.empty = 0
        self.failed = 0
        self.sha_verified = 0
        self.sha_failures = 0
        self.files_declared = 0
        self.files_present = 0
        self.orphan_files = 0
        self.missing_files = 0

    def count(self, outcome):
        self.expected += 1
        if outcome == NONEMPTY:
            self.nonempty += 1
        elif outcome == EMPTY:
            self.empty += 1
        else:
            self.failed += 1

    def block(self):
        return {
            'expected_requests': self.expected,
            'successful_requests': self.nonempty + self.empty,
            'success_nonempty': self.nonempty,
            'success_empty': self.empty,
            'failed_requests': self.failed,
            'sha_verified': self.sha_verified,
            'sha_failures': self.sha_failures,
            'files_declared': self.files_declared,
            'files_present': self.files_present,
            'orphan_files': self.orphan_files,
            'missing_files': self.missing_files,
        }


def sha256_of(fp: Path) -> str:
    h = hashlib.sha256()
    h.update(fp.read_bytes())
    return h.hexdigest()


def port_open(port: int, host='127.0.0.1', timeout=2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def pid_of_listener() -> int | None:
    try:
        out = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             "(Get-NetTCPConnection -LocalPort 17709 -State Listen | Select-Object -First 1).OwningProcess"],
            capture_output=True, text=True, timeout=15).stdout.strip()
        return int(out) if out.isdigit() else None
    except Exception:
        return None


def ensure_client(max_wait_s: int = 240) -> int | None:
    if port_open(17709):
        return pid_of_listener()
    if not TDX_EXE.exists():
        print(f'client exe missing: {TDX_EXE}', file=sys.stderr)
        return None
    subprocess.Popen([str(TDX_EXE)], cwd=str(CLIENT_DIR))
    deadline = time.time() + max_wait_s
    while time.time() < deadline:
        if port_open(17709):
            time.sleep(5)
            return pid_of_listener()
        time.sleep(5)
    return None


def tqcenter_version() -> str:
    try:
        txt = (USER_DIR / 'tqcenter.py').read_text(encoding='utf-8', errors='ignore')
        m = re.search(r"Version[:=]\s*[\"']?([\d.]+)", txt)
        if m:
            return m.group(1)
    except Exception:
        pass
    return 'unknown'


def add_entry(manifest: list, ctr: Counters, name: str, request: str,
              outcome: str, fp: Path | None, day_dir: Path, error: str | None = None):
    entry = {'name': name, 'request': request, 'outcome': outcome}
    if error:
        entry['error'] = error[:300]
    if outcome == NONEMPTY and fp is not None and fp.exists():
        rel = str(fp.relative_to(day_dir))
        entry['file'] = rel
        entry['bytes'] = fp.stat().st_size
        entry['sha256'] = sha256_of(fp)
        entry['retrieved_at'] = datetime.now(timezone.utc).isoformat()
    manifest.append(entry)
    ctr.count(outcome)


def fetch_file_artifact(kind: str, code: str, down_time: str, dtype: int,
                        day_dir: Path, ctr: Counters, manifest: list, day_label: str):
    """download_file based artifact with strict outcome classification."""
    num = code.split('.')[0]
    name = f'{kind}_{code}'
    request = f'download_file({code!r},{down_time!r},{dtype})'
    try:
        msg = tq.download_file(code, down_time, dtype)
        src = DATA_DIR / src_name(kind, num, down_time)
        if src.exists() and src.stat().st_size > 2:
            dst_name = (f'pcf_{num}_{down_time}.json' if kind == 'pcf'
                        else f'holders_{num}_{down_time[:4]}.json' if kind == 'holders'
                        else f'{kind}_{num}_{day_label}.json')
            dst = day_dir / dst_name
            dst.write_bytes(src.read_bytes())
            add_entry(manifest, ctr, name, request, NONEMPTY, dst, day_dir)
        else:
            add_entry(manifest, ctr, name, request, EMPTY, None, day_dir,
                      error=f'download ok, no non-empty file ({msg})')
    except Exception as exc:
        add_entry(manifest, ctr, name, request, FAILED, None, day_dir, error=repr(exc))


def verify_shas(manifest: list, ctr: Counters, day_dir: Path):
    for a in manifest:
        if a.get('sha256') and a.get('file'):
            fp = day_dir / a['file']
            try:
                if sha256_of(fp) == a['sha256']:
                    ctr.sha_verified += 1
                    continue
            except Exception:
                pass
            ctr.sha_failures += 1
            a['sha_recheck'] = 'MISMATCH_OR_UNREADABLE'


def enforce_file_invariant(manifest: list, ctr: Counters, day_dir: Path):
    """actual files must equal manifest-declared files (manifest.json aside)."""
    declared = {a['file'] for a in manifest if a.get('file')}
    actual = {p.name for p in day_dir.iterdir() if p.is_file()} - {'manifest.json'}
    ctr.files_declared = len(declared)
    ctr.files_present = len(actual & declared)
    ctr.orphan_files = len(actual - declared)
    ctr.missing_files = len(declared - actual)


def load_frozen_universe() -> tuple[list[str], str]:
    """Universe is a frozen contract: any damage is fatal, never a shrink."""
    try:
        raw = UNIVERSE_FILE.read_bytes()
        codes = json.loads(raw.decode('utf-8'))['codes']
    except Exception as exc:
        raise RuntimeError(f'universe file unreadable ({UNIVERSE_FILE}): {exc!r} — '
                           f'refusing to shrink expected request set') from exc
    if len(codes) != UNIVERSE_FROZEN_SIZE:
        raise RuntimeError(f'universe size {len(codes)} != frozen {UNIVERSE_FROZEN_SIZE} '
                           f'(baseline {UNIVERSE_BASELINE_COMMIT})')
    if len(set(codes)) != len(codes):
        raise RuntimeError('universe contains duplicate codes')
    return codes, hashlib.sha256(raw).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--date', default=datetime.now().strftime('%Y%m%d'))
    args = ap.parse_args()

    day_dir = ARCHIVE_ROOT / args.date
    day_dir.mkdir(parents=True, exist_ok=True)
    manifest_fp = day_dir / 'manifest.json'

    if manifest_fp.exists() and not args.force:
        try:
            man = json.loads(manifest_fp.read_text(encoding='utf-8'))
            if man.get('status') == 'COMPLETE':
                print(f'already archived for {args.date}; use --force')
                return 0
        except Exception:
            pass

    # --force owns the day directory: clear stale artifacts so reruns cannot leak orphans
    if args.force:
        for p in day_dir.iterdir():
            if p.is_file() and p.name != 'manifest.json':
                p.unlink()

    ctr = Counters()
    manifest = []
    fatal = None
    tq_up = False
    meta = {}
    day_type = ('holders' if (datetime.strptime(args.date, '%Y%m%d').weekday() == 0 or args.force)
                else 'regular')

    try:
        codes, universe_sha = load_frozen_universe()
        expected_contract = (len(MARKET_SNAPSHOTS) + len(ETF_WATCHLIST) + 1
                             + 2 * min(LHB_UNLOCK_WINDOW, len(codes))
                             + (len(codes) if day_type == 'holders' else 0))
        meta = {
            'node': 'tdx-node free account',
            'archivist_version': '1.2.0',
            'tqcenter_version': tqcenter_version(),
            'client_pid': None,
            'http_plane': '127.0.0.1:17709',
            'day_type': day_type,
            'universe_size': len(codes),
            'universe_sha256': universe_sha,
            'universe_baseline_commit': UNIVERSE_BASELINE_COMMIT,
            'expected_contract': expected_contract,
            'contract_note': 'gb_today_watchlist is ONE grouped request (audit option B): '
                             'regular day = 4 markets + 8 PCF + 1 gb group + 20 LHB + 20 unlock = 53; '
                             'holders day adds 84 = 137',
            'status_ladder': 'COMPLETE(all mandatory fetches ok + contract met + sha + file invariant) '
                             '/ PARTIAL(some failed) / FAILED(fatal)',
            'red_lines': [
                'ETF get_gb_info_by_date never used (false history, unique_zgb=1)',
                'GP52/GP03-series gated by paid package — not fetched',
            ],
        }

        pid = ensure_client()
        meta['client_pid'] = pid
        if pid is None:
            raise RuntimeError('client plane 127.0.0.1:17709 not available and could not be started')

        tq.initialize(str(USER_DIR / 'daily_archive_anchor.py'))
        tq_up = True

        # 1) market category snapshots (list_type=1 returns Code+Name; 2/3 return empty)
        for mkt, label in MARKET_SNAPSHOTS.items():
            request = f'get_stock_list({mkt!r}, list_type=1)'
            try:
                rows = tq.get_stock_list(mkt, list_type=1)
                if rows:
                    fp = day_dir / f'{label}.json'
                    fp.write_text(json.dumps(rows, ensure_ascii=False, indent=1, default=str),
                                  encoding='utf-8')
                    add_entry(manifest, ctr, label, request, NONEMPTY, fp, day_dir)
                else:
                    add_entry(manifest, ctr, label, request, EMPTY, None, day_dir,
                              error='empty list returned')
            except Exception as exc:
                add_entry(manifest, ctr, label, request, FAILED, None, day_dir, error=repr(exc))

        # 2) ETF PCF for watchlist
        for code in ETF_WATCHLIST:
            fetch_file_artifact('pcf', code, args.date, 2, day_dir, ctr, manifest, args.date)
            time.sleep(0.2)

        # 3) today's share-capital snapshot — ONE grouped request over the frozen universe
        gb_tally = {'n_nonempty': 0, 'n_empty': 0, 'n_failed': 0}
        gb_today = {}
        for code in codes:
            try:
                rows = tq.get_gb_info_by_date(code, args.date, args.date)
                gb_today[code] = rows[-1] if rows else None
                gb_tally['n_nonempty' if rows else 'n_empty'] += 1
            except Exception as exc:
                gb_today[code] = {'error': repr(exc)}
                gb_tally['n_failed'] += 1
            time.sleep(0.1)
        if sum(gb_tally.values()) != len(codes):
            raise RuntimeError(f'gb tally {gb_tally} does not sum to universe size {len(codes)}')
        fp = day_dir / 'gb_today_watchlist.json'
        payload = {
            'as_of': args.date,
            'universe_size': len(codes),
            'tally': gb_tally,
            'warning': 'single-date snapshot; historical backfill of this field is current-snapshot '
                       'backfilled by TDX for ETFs and is NOT point-in-time for anything before archive start',
            'stocks': gb_today,
        }
        fp.write_text(json.dumps(payload, ensure_ascii=False, indent=1, default=str), encoding='utf-8')
        group_outcome = FAILED if gb_tally['n_failed'] else NONEMPTY
        add_entry(manifest, ctr, 'gb_today_watchlist',
                  f'get_gb_info_by_date(code,{args.date},{args.date}) grouped x {len(codes)}',
                  group_outcome, fp, day_dir)
        manifest[-1]['tally'] = gb_tally

        # 4) LHB + unlock recent files (first 20 codes to stay light)
        for kind, dtype in (('lhb', 6), ('unlock', 7)):
            for code in codes[:LHB_UNLOCK_WINDOW]:
                fetch_file_artifact(kind, code, args.date, dtype, day_dir, ctr, manifest, args.date)
                time.sleep(0.15)

        # 5) holders for current year — holders day only (Monday or --force)
        if day_type == 'holders':
            year = args.date[:4]
            for code in codes:
                fetch_file_artifact('holders', code, f'{year}0101', 1, day_dir, ctr, manifest, args.date)
                time.sleep(0.15)
    except BaseException as exc:
        fatal = f'{type(exc).__name__}: {exc}'
        manifest.append({'name': '__fatal__', 'outcome': FAILED, 'error': fatal,
                         'traceback': traceback.format_exc()})
    finally:
        if tq_up:
            try:
                tq.close()
            except Exception:
                pass

    verify_shas(manifest, ctr, day_dir)
    enforce_file_invariant(manifest, ctr, day_dir)

    contract = meta.get('expected_contract')
    contract_met = contract is not None and ctr.expected == contract
    if fatal is not None or not manifest or (contract is not None and not contract_met):
        status = 'FAILED'
    elif (ctr.failed == 0 and ctr.sha_failures == 0
          and ctr.orphan_files == 0 and ctr.missing_files == 0):
        status = 'COMPLETE'
    else:
        status = 'PARTIAL'

    out = {'date': args.date, 'status': status,
           'fatal': fatal,
           'contract_met': contract_met,
           'completed_at': datetime.now(timezone.utc).isoformat(),
           'meta': meta, 'completeness': ctr.block(), 'artifacts': manifest}
    manifest_fp.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding='utf-8')
    print(json.dumps({'date': args.date, 'status': status, 'contract_met': contract_met,
                      'completeness': ctr.block()}, ensure_ascii=False))
    return 0 if status == 'COMPLETE' else (1 if status == 'PARTIAL' else 2)


if __name__ == '__main__':
    sys.exit(main())
