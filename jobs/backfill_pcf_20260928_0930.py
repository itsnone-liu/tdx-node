#!/usr/bin/env python3
"""One-off PCF backfill for the archivist outage window 20260928-20260930.

Outage postmortem: the TDX client's auto-login stopped working after
2026-09-27, so every daily run 20260928..20261004 died at the login dialog
(fatal: client plane 17709 not available). Snapshot sources for those days
(market lists, gb_today, LHB, unlock) are unrecoverable — that gap stays
honest in the FAILED day manifests. PCF files, however, are downloaded
per-date (download_file(code, down_time, 2)) and the server still serves
past dates (probe 2026-10-05: etfpcf510300_20260929.json OK).

This script backfills ONLY the PCF artifacts for the three lost TRADING
days (2026-10-01..10-08 is the National Day holiday; 10-04/05 weekend).
Files land in archive/backfill_pcf_20260928_0930/ — deliberately NOT in
the per-day directories, whose FAILED manifests must keep recording the
outage (adding files there would break the orphan-files invariant).

No credentials are read; the client's logged-in session is the only auth.
"""
from __future__ import annotations
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

NODE_ROOT = Path(r'D:\tdx-node')
CLIENT_DIR = NODE_ROOT / 'tdx-tq-v773'
USER_DIR = CLIENT_DIR / 'PYPlugins' / 'user'
DATA_DIR = CLIENT_DIR / 'PYPlugins' / 'data'

sys.path.insert(0, str(USER_DIR))
from tqcenter import tq  # noqa: E402

ETF_WATCHLIST = [
    '510300.SH', '510050.SH', '159919.SZ', '159915.SZ',
    '512880.SH', '518880.SH', '513050.SH', '512100.SH',
]
DAYS = ['20260928', '20260929', '20260930']
OUT_DIR = NODE_ROOT / 'archive' / 'backfill_pcf_20260928_0930'

NONEMPTY, EMPTY = 'SUCCESS_NONEMPTY', 'SUCCESS_EMPTY'


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tq.initialize(str(USER_DIR / 'daily_archive_anchor.py'))
    manifest = []
    for day in DAYS:
        for code in ETF_WATCHLIST:
            num = code.split('.')[0]
            name = f'pcf_{code}'
            request = f'download_file({code!r},{day!r},2)'
            try:
                msg = tq.download_file(code, day, 2)
                src = DATA_DIR / f'etfpcf{num}_{day}.json'
                entry = {'name': name, 'request': request}
                if src.exists() and src.stat().st_size > 2 and b'Error' not in src.read_bytes()[:40]:
                    dst = OUT_DIR / f'pcf_{num}_{day}.json'
                    dst.write_bytes(src.read_bytes())
                    entry['outcome'] = NONEMPTY
                    entry['file'] = dst.name
                    entry['bytes'] = dst.stat().st_size
                    entry['sha256'] = hashlib.sha256(dst.read_bytes()).hexdigest()
                else:
                    entry['outcome'] = EMPTY
                    entry['error'] = f'no non-empty file ({msg})'
                manifest.append(entry)
                time.sleep(0.2)
            except Exception as exc:
                manifest.append({'name': name, 'request': request,
                                 'outcome': 'FAILED', 'error': repr(exc)[:300]})

    n_nonempty = sum(1 for e in manifest if e['outcome'] == NONEMPTY)
    doc = {
        'kind': 'pcf-backfill',
        'reason': 'archivist outage 20260928-20261004 (client login dialog, auto-login broken); '
                  'PCF is per-date server-side, lost trading days recovered',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'days': DAYS,
        'etfs': ETF_WATCHLIST,
        'completeness': {
            'expected_requests': len(manifest),
            'success_nonempty': n_nonempty,
            'success_empty': sum(1 for e in manifest if e['outcome'] == EMPTY),
            'failed': sum(1 for e in manifest if e['outcome'] == 'FAILED'),
        },
        'artifacts': manifest,
    }
    (OUT_DIR / 'manifest.json').write_text(
        json.dumps(doc, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(doc['completeness'], ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
