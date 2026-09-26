#!/usr/bin/env python3
"""Task 1: share-capital history probe with change-point extraction and dividend cross-check.

Universe is pluggable:
  --universe path.json   JSON list of codes like ["600519.SH", ...]
  --csi300               use tq.get_stock_list(market='23') as provisional universe

Outputs (small, commit-friendly):
  <output>            summary + per-stock change points + gate statistics
  --raw-dir           full daily series per stock (archive only, git-ignored)
"""
from __future__ import annotations
import argparse
import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from tqcenter import tq  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument('--universe')
parser.add_argument('--csi300', action='store_true')
parser.add_argument('--start', default='20210101')
parser.add_argument('--end', default='20260924')
parser.add_argument('--output', required=True)
parser.add_argument('--raw-dir')
parser.add_argument('--max-stocks', type=int, default=0)
args = parser.parse_args()

raw_dir = Path(args.raw_dir) if args.raw_dir else None
if raw_dir:
    raw_dir.mkdir(parents=True, exist_ok=True)

out = {
    'captured_at': datetime.now(timezone.utc).isoformat(),
    'start': args.start,
    'end': args.end,
    'universe_source': None,
    'stocks': {},
    'gate': {},
}


def change_points(rows):
    pts = []
    prev = None
    for r in rows:
        cur = (r.get('Zgb'), r.get('Ltgb'))
        if prev is not None and (cur[0] != prev[0] or cur[1] != prev[1]):
            pts.append({
                'date': r['Date'],
                'zgb_prev': prev[0], 'zgb_new': cur[0],
                'ltgb_prev': prev[1], 'ltgb_new': cur[1],
                'zgb_ratio': (cur[0] / prev[0]) if prev[0] else None,
                'ltgb_ratio': (cur[1] / prev[1]) if prev[1] else None,
            })
        prev = cur
    return pts


def d8(s):
    s = str(s)[:10].replace('-', '').replace('/', '')
    return s.replace(' 00:00:00', '')


try:
    tq.initialize(__file__)

    if args.universe:
        loaded = json.loads(Path(args.universe).read_text(encoding='utf-8'))
        universe = loaded['codes'] if isinstance(loaded, dict) else loaded
        out['universe_source'] = str(args.universe)
    else:
        universe = [x['Code'] if isinstance(x, dict) else x
                    for x in tq.get_stock_list('23', list_type=1)]
        out['universe_source'] = 'tq.get_stock_list(market=23) [provisional]'
    if args.max_stocks:
        universe = universe[:args.max_stocks]
    out['universe_size'] = len(universe)

    matched = 0
    unmatched = 0
    errors = 0
    flat_stocks = []
    for i, code in enumerate(universe, 1):
        try:
            rows = tq.get_gb_info_by_date(code, args.start, args.end)
            if not rows:
                out['stocks'][code] = {'status': 'empty'}
                errors += 1
                continue
            pts = change_points(rows)
            try:
                dv_raw = tq.get_divid_factors(code, args.start, args.end)
                if hasattr(dv_raw, 'reset_index'):
                    dv = dv_raw.reset_index().to_dict('records')
                else:
                    dv = list(dv_raw or [])
            except Exception:
                dv = []
            divid_dates = [d8(x.get('Date', '')) for x in dv]

            def near_divid(ptdate):
                pd_ = str(ptdate)
                for dd in divid_dates:
                    try:
                        delta = abs((datetime.strptime(pd_, '%Y%m%d') - datetime.strptime(dd, '%Y%m%d')).days)
                    except ValueError:
                        continue
                    if delta <= 10:
                        return dd
                return None

            for p in pts:
                p['divid_match'] = near_divid(p['date'])
                if p['divid_match']:
                    matched += 1
                else:
                    unmatched += 1
            rec = {
                'status': 'ok',
                'rows': len(rows),
                'first': rows[0]['Date'],
                'last': rows[-1]['Date'],
                'unique_zgb': len({r['Zgb'] for r in rows}),
                'unique_ltgb': len({r['Ltgb'] for r in rows}),
                'changes': pts,
                'divid_events': [{'date': d8(x.get('Date', '')),
                                  'type': x.get('Type'),
                                  'share_bonus': x.get('ShareBonus'),
                                  'allotment': x.get('Allotment')} for x in dv],
            }
            out['stocks'][code] = rec
            if not pts:
                flat_stocks.append(code)
            if raw_dir:
                (raw_dir / f'{code}.json').write_text(
                    json.dumps(rows, ensure_ascii=False, default=str), encoding='utf-8')
            if i % 25 == 0:
                print(f'progress {i}/{len(universe)}', flush=True)
            time.sleep(0.05)
        except Exception as exc:
            out['stocks'][code] = {'status': 'error', 'error': repr(exc)}
            errors += 1

    total_changes = matched + unmatched
    out['gate'] = {
        'stocks_ok': sum(1 for v in out['stocks'].values() if v.get('status') == 'ok'),
        'stocks_flat_no_change': len(flat_stocks),
        'stocks_error': errors,
        'change_points_total': total_changes,
        'change_matched_divid_within_10d': matched,
        'change_unmatched': unmatched,
        'match_rate': round(matched / total_changes, 4) if total_changes else None,
        'note': 'unmatched changes are expected for 增发/回购注销/股权激励; they need external verification, not necessarily errors',
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
print(json.dumps({'status': out.get('status'), 'universe': out.get('universe_size'),
                  'gate': out.get('gate')}, ensure_ascii=False, indent=2))
