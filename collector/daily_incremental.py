#!/usr/bin/env python3
"""Daily incremental collector: append today's (or a given day's) LHB +
block trades + margin from official endpoints, then renormalize CSVs.

Designed for the evening archivist slot (or Task Scheduler). Sequential
SZSE access only; refuses to run while a backfill holds its lock.

Usage:
  python daily_incremental.py                 # last completed trading day
  python daily_incremental.py --date 20261009
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

NODE = Path(r'D:\tdx-node')
sys.path.insert(0, str(NODE / 'collector'))


def load_calendar() -> list[str]:
    days = set()
    for fp in (NODE / 'manifests' / 'trading_calendar_2021_2026.json',
               NODE / 'manifests' / 'calendar_prefill_2021.json'):
        if fp.exists():
            days.update(json.loads(fp.read_text(encoding='utf-8')))
    return sorted(days)


def lock_held() -> bool:
    import ctypes
    for lk in (NODE / 'lhb' / '.backfill.lock',
               NODE / 'blockmargin' / '.bm_backfill.lock'):
        if lk.exists():
            try:
                pid = int(lk.read_text().strip())
                h = ctypes.windll.kernel32.OpenProcess(0x00100000, False, pid)
                if h:
                    ctypes.windll.kernel32.CloseHandle(h)
                    return True
            except (ValueError, OSError, AttributeError):
                pass
    return False


def run(cmd, what) -> bool:
    print(f'>>> {what}', flush=True)
    r = subprocess.run([sys.executable] + cmd, cwd=str(NODE))
    print(f'<<< {what}: exit {r.returncode}', flush=True)
    return r.returncode == 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', help='YYYYMMDD; default = last trading day')
    args = ap.parse_args()

    if lock_held():
        print('backfill lock held — skip this daily run', flush=True)
        return 2

    cal = load_calendar()
    if not cal:
        print('no calendar', flush=True)
        return 3
    if args.date:
        day = args.date
    else:
        today = datetime.now().strftime('%Y%m%d')
        day = max((d for d in cal if d <= today), default=None)
        if not day:
            print('calendar has no day <= today', flush=True)
            return 3
    print(f'daily incremental for {day}', flush=True)

    ok = True
    # ① LHB
    ok &= run([str(NODE / 'collector' / 'lhb_backfill.py'),
               '--dates', day], f'lhb {day}')
    # ②③ block + margin (SSE then SZSE, sequential)
    ok &= run([str(NODE / 'collector' / 'block_margin_backfill.py'),
               'block', 'sse', '--dates', day], f'block/sse {day}')
    ok &= run([str(NODE / 'collector' / 'block_margin_backfill.py'),
               'block', 'szse', '--dates', day], f'block/szse {day}')
    ok &= run([str(NODE / 'collector' / 'block_margin_backfill.py'),
               'margin', 'sse', '--dates', day], f'margin/sse {day}')
    ok &= run([str(NODE / 'collector' / 'block_margin_backfill.py'),
               'margin', 'szse', '--dates', day], f'margin/szse {day}')
    # renormalize (idempotent full rebuild from raw, seconds)
    ok &= run([str(NODE / 'collector' / 'lhb_normalize.py')], 'lhb normalize')
    ok &= run([str(NODE / 'collector' / 'block_normalize.py')], 'block normalize')
    ok &= run([str(NODE / 'collector' / 'margin_normalize.py')], 'margin normalize')
    print('DAILY DONE' if ok else 'DAILY COMPLETED WITH ERRORS', flush=True)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
