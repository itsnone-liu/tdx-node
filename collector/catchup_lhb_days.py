#!/usr/bin/env python3
"""Catch-up: re-run any LHB day whose state is not COMPLETE (FAILED or
PARTIAL). Full reprocess is safe: raw files are append-only, so this only
re-fetches what is missing (e.g. list page 2 that never got saved)."""
import json
import os
import subprocess
import sys
from pathlib import Path

NODE = Path(os.environ.get('TDX_NODE') or r'D:\tdx-node').expanduser()  # TDX_NODE env → Linux/米线; 默认仍是 Windows D:\tdx-node
STATE_FP = NODE / 'lhb' / 'backfill_state.json'


def main() -> int:
    state = json.loads(STATE_FP.read_text(encoding='utf-8'))
    bad = sorted(d for d, v in state.items()
                 if v.get('status') not in ('COMPLETE',))
    # also days fully absent from state within the covered window
    if not bad:
        print('nothing to catch up')
        return 0
    print(f'catch-up days: {bad}')
    r = subprocess.run([sys.executable,
                        str(NODE / 'collector' / 'lhb_backfill.py'),
                        '--dates', ','.join(bad)], cwd=str(NODE))
    return r.returncode


if __name__ == '__main__':
    sys.exit(main())
