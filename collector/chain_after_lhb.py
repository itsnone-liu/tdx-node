#!/usr/bin/env python3
"""Chain orchestrator: wait for the LHB backfill to finish, then run the
SZSE-only queue strictly sequentially (one SZSE consumer at a time — see
LHB_PIPELINE.md), then normalize + crosscheck gate.

Polls lhb/backfill_run.log for a FINISHED line (with a hard timeout).
"""
import os
import subprocess
import sys
import time
from pathlib import Path

NODE = Path(os.environ.get('TDX_NODE') or r'D:\tdx-node').expanduser()  # TDX_NODE env → Linux/米线; 默认仍是 Windows D:\tdx-node
LHB_LOG = NODE / 'lhb' / 'backfill_run.log'
TIMEOUT_S = 14 * 3600  # generous: LHB eta ~9h
PY = sys.executable

CHAIN = [
    [PY, str(NODE / 'collector' / 'lhb_backfill.py'), '--repair'],
    [PY, str(NODE / 'collector' / 'catchup_lhb_days.py')],
    [PY, str(NODE / 'probes' / 'probe_szse_xlsx.py')],
    [PY, str(NODE / 'collector' / 'block_margin_backfill.py'), 'block', 'szse'],
    [PY, str(NODE / 'collector' / 'block_margin_backfill.py'), 'margin', 'szse'],
    [PY, str(NODE / 'collector' / 'lhb_normalize.py')],
    [PY, str(NODE / 'collector' / 'block_normalize.py')],
    [PY, str(NODE / 'collector' / 'margin_normalize.py')],
    [PY, str(NODE / 'collector' / 'lhb_crosscheck_tdx.py')],
    [PY, str(NODE / 'collector' / 'quality_audit.py')],
    [PY, str(NODE / 'collector' / 'make_delivery_report.py')],
]


def lhb_finished() -> bool:
    try:
        tail = LHB_LOG.read_text(encoding='utf-8', errors='replace')[-4000:]
    except OSError:
        return False
    lines = [l for l in tail.splitlines() if l.strip()]
    return bool(lines) and lines[-1].startswith('FINISHED')


def main() -> int:
    print('waiting for LHB backfill to finish...', flush=True)
    t0 = time.time()
    while not lhb_finished():
        if time.time() - t0 > TIMEOUT_S:
            print('TIMEOUT waiting for LHB — aborting chain', flush=True)
            return 3
        time.sleep(120)
    print('LHB backfill finished; running SZSE chain sequentially', flush=True)
    for cmd in CHAIN:
        print(f'>>> {" ".join(cmd)}', flush=True)
        r = subprocess.run(cmd, cwd=str(NODE))
        print(f'<<< exit {r.returncode}', flush=True)
        if r.returncode not in (0, 1):  # gate may exit 1 on mismatch; keep going
            return r.returncode
    print('CHAIN DONE', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
