#!/usr/bin/env python3
"""Task 2: batch-download top-10 holders files for the CSR-84 universe and assess content coverage.

Coverage assessment only (CONTENT level, not PIT): snapshot dates found per stock/year,
gd/ltgd presence, holder counts. Publication-date chain is out of scope here.

Universe: --universe path.json  (dict with 'codes' or plain list, TDX style '600519.SH')
Years:    --years 2021,2022,2023,2024,2025,2026
Outputs:
  <output>          coverage summary (small, commit-friendly)
  --parsed-dir      normalized snapshots {code, year, snapshots:{date:{gd,ltgd}}} (archive)
"""
from __future__ import annotations
import argparse
import json
import shutil
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from tqcenter import tq  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument('--universe', required=True)
parser.add_argument('--years', default='2021,2022,2023,2024,2025,2026')
parser.add_argument('--output', required=True)
parser.add_argument('--parsed-dir')
parser.add_argument('--sleep', type=float, default=0.3)
parser.add_argument('--max-stocks', type=int, default=0)
args = parser.parse_args()

years = [int(y) for y in args.years.split(',')]
parsed_dir = Path(args.parsed_dir) if args.parsed_dir else None
if parsed_dir:
    parsed_dir.mkdir(parents=True, exist_ok=True)
data_dir = HERE.parent / 'data'

out = {
    'captured_at': datetime.now(timezone.utc).isoformat(),
    'universe_source': str(args.universe),
    'years': years,
    'disclaimer': 'content coverage only; holder snapshot dates are NOT publication dates; PIT requires official announcement-date join',
    'stocks': {},
    'summary': {},
}


def normalize_file(fp: Path):
    """Parse holders<code>_<year>.json -> {date: {gd: [...], ltgd: [...]}} or None."""
    try:
        arr = json.loads(fp.read_text(encoding='utf-8'))
    except Exception:
        return None
    if not isinstance(arr, list):
        return None
    snaps = {}
    for entry in arr:
        inner = entry.get('gdxx') if isinstance(entry, dict) else None
        if not inner:
            continue
        try:
            obj = json.loads(inner)
        except Exception:
            continue
        for date, payload in obj.items():
            if isinstance(payload, dict):
                snaps[date] = {'gd': payload.get('gd', []),
                               'ltgd': payload.get('ltgd', [])}
    return snaps or None


try:
    tq.initialize(__file__)

    loaded = json.loads(Path(args.universe).read_text(encoding='utf-8'))
    universe = loaded['codes'] if isinstance(loaded, dict) else loaded
    if args.max_stocks:
        universe = universe[:args.max_stocks]
    out['universe_size'] = len(universe)

    total_calls = 0
    total_files = 0
    total_snapshots = 0
    dl_errors = 0
    for i, code in enumerate(universe, 1):
        num = code.split('.')[0]
        rec = {'years': {}, 'errors': []}
        for year in years:
            try:
                msg = tq.download_file(code, f'{year}0101', 1)
                total_calls += 1
                fp = data_dir / f'holders{num}_{year}.json'
                year_rec = {'msg': str(msg)[:120], 'file': fp.name, 'exists': fp.exists()}
                if fp.exists():
                    snaps = normalize_file(fp)
                    if snaps:
                        dates = sorted(snaps.keys())
                        year_rec.update({
                            'snapshots': len(dates),
                            'first': dates[0],
                            'last': dates[-1],
                            'ltgd_dates': sum(1 for d in dates if snaps[d].get('ltgd')),
                            'gd_rows_first_date': len(snaps[dates[-1]]['gd']) if dates else 0,
                        })
                        total_snapshots += len(dates)
                        total_files += 1
                        if parsed_dir:
                            dest = parsed_dir / f'holders{num}_{year}.json'
                            dest.write_text(json.dumps(
                                {'code': code, 'year': year, 'snapshots': snaps},
                                ensure_ascii=False, indent=1), encoding='utf-8')
                    else:
                        year_rec['parse'] = 'empty_or_unparseable'
                rec['years'][year] = year_rec
                time.sleep(args.sleep)
            except Exception as exc:
                rec['errors'].append(f'{year}: {exc!r}')
                dl_errors += 1
        yrs_ok = [y for y, r in rec['years'].items() if r.get('snapshots')]
        all_dates = []
        for y, r in rec['years'].items():
            if r.get('snapshots'):
                pass
        rec['years_with_data'] = yrs_ok
        rec['total_snapshots'] = sum(rec['years'][y]['snapshots'] for y in yrs_ok)
        if rec['total_snapshots']:
            rec['earliest'] = min(rec['years'][y]['first'] for y in yrs_ok)
            rec['latest'] = max(rec['years'][y]['last'] for y in yrs_ok)
        out['stocks'][code] = rec
        if i % 10 == 0:
            print(f'progress {i}/{len(universe)} snapshots={total_snapshots}', flush=True)

    stocks_any = sum(1 for v in out['stocks'].values() if v['total_snapshots'] > 0)
    out['summary'] = {
        'stocks_total': len(universe),
        'stocks_with_any_holders': stocks_any,
        'download_calls': total_calls,
        'files_parsed': total_files,
        'download_errors': dl_errors,
        'total_snapshot_dates': total_snapshots,
    }
    out['status'] = 'success'
except BaseException as exc:
    out.update(status='error', error_type=type(exc).__name__, error=str(exc),
               traceback=traceback.format_exc())
finally:
    try:
        tq.close()
    except Exception:
        pass

Path(args.output).parent.mkdir(parents=True, exist_ok=True)
Path(args.output).write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str) + '\n', encoding='utf-8')
print(json.dumps({'status': out.get('status'), 'summary': out.get('summary')}, ensure_ascii=False, indent=2))
