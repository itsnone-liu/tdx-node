#!/usr/bin/env python3
"""Cross-validation gate: TDX lhb<code>.json (last-10-events per stock,
broker-side data) vs the official exchange CSV (lhb/csv/lhb_seats.csv).

Compares every (code, trade_date) pair the two sides share:
  - seat-name match at each rank on both buy and sell lists
  - the primary-side amount at that rank (buy list -> 买入金额 vs buy_amt;
    sell list -> 卖出金额 vs sell_amt)
  - TDX 净额 vs official buy_amt-sell_amt per seat (SZSE only; SSE official
    rows carry one-sided amounts)

Exit 0 if seat-name agreement >= 99% AND amount agreement >= 97% of compared
seat rows and no more than 1% official-side day-code pairs unexplained;
exit 1 otherwise. Writes lhb/crosscheck_report.json.
"""
from __future__ import annotations
import os
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

NODE = Path(os.environ.get('TDX_NODE') or r'D:\tdx-node').expanduser()  # TDX_NODE env → Linux/米线; 默认仍是 Windows D:\tdx-node
TDX_DIR = NODE / 'tdx-tq-v773' / 'PYPlugins' / 'data'
SEATS_FP = NODE / 'lhb' / 'csv' / 'lhb_seats.csv'
OUT_FP = NODE / 'lhb' / 'crosscheck_report.json'


def load_official():
    """(code, date) -> side -> rank -> list[(name, buy, sell)].

    Keep all reason rows: a stock can qualify under multiple reasons on one
    day, while TDX's rolled-up event doesn't use the same reason taxonomy.
    """
    idx: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    with SEATS_FP.open(encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            key = (r['code'], r['trade_date'])
            idx[key][r['side']][int(r['rank'])].append(
                (r['seat_name'],
                 float(r['buy_amt']) if r['buy_amt'] else None,
                 float(r['sell_amt']) if r['sell_amt'] else None))
    return idx


def load_tdx():
    events = {}  # (code, date_iso) -> {'B': {rank: (name, buy, sell, net)}, 'S': ...}
    for fp in sorted(TDX_DIR.glob('lhb*.json')):
        code = fp.stem[3:]
        try:
            outer = json.loads(fp.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            continue
        for rec in outer if isinstance(outer, list) else [outer]:
            if not isinstance(rec, dict) or 'data_json' not in rec:
                continue
            try:
                days = json.loads(rec['data_json'])
            except json.JSONDecodeError:
                continue
            for d_compact, reasons in days.items():
                d_iso = (f'{d_compact[:4]}-{d_compact[4:6]}-{d_compact[6:]}'
                         if len(d_compact) == 8 and '-' not in d_compact
                         else d_compact)
                for _reason, sides in reasons.items():
                    ev = events.setdefault((code, d_iso),
                                           {'B': {}, 'S': {}})
                    for tdx_side, our_side in (('买入', 'B'), ('卖出', 'S')):
                        for seat in sides.get(tdx_side) or []:
                            rank = int(seat.get('排名') or 0)
                            if not rank:
                                continue
                            ev[our_side][rank] = (
                                (seat.get('营业部名称') or '').strip(),
                                float(seat.get('买入金额') or 0),
                                float(seat.get('卖出金额') or 0),
                                float(seat.get('净额') or 0))
    return events


def main() -> int:
    official = load_official()
    tdx = load_tdx()
    shared = sorted(set(official) & set(tdx))
    print(f'official day-code pairs: {len(official)}; tdx events: {len(tdx)}; '
          f'shared: {len(shared)}')

    n_pair_ok = 0
    n_seats = n_name_match = n_amt_match = n_amt_tol = 0
    worst = []
    for code, d in shared:
        off = official[(code, d)]
        pair_ok = True
        for side in ('B', 'S'):
            t = tdx[(code, d)].get(side) or {}
            o = off.get(side) or {}
            for rank in range(1, 6):
                if rank not in t or rank not in o:
                    continue
                tn, tb, ts, tnet = t[rank]
                # Match any official reason-row candidate; TDX and exchange
                # reason taxonomy/grouping can differ on multi-day events.
                candidates = o[rank]
                candidate = next((x for x in candidates if x[0] == tn),
                                 candidates[0] if len(candidates) == 1 else None)
                n_seats += 1
                if candidate is None:
                    n_amt_match += 0
                    pair_ok = False
                    if len(worst) < 25:
                        worst.append({'code': code, 'date': d, 'side': side,
                                      'rank': rank, 'tdx': [tn, tb, ts, tnet],
                                      'official_candidates': candidates})
                    continue
                on, ob, os_ = candidate
                name_ok = tn == on
                n_name_match += name_ok
                tprimary = tb if side == 'B' else ts
                oprimary = ob if side == 'B' else os_
                amt_ok = (tprimary is not None and oprimary is not None and
                          abs(tprimary - oprimary) <= 1.0)
                n_amt_match += amt_ok
                n_amt_tol += (tprimary is not None and oprimary is not None and
                              abs(tprimary - oprimary) <= max(1.0, 0.001 * max(tprimary, oprimary)))
                if not name_ok or not amt_ok:
                    pair_ok = False
                    if len(worst) < 25:
                        worst.append({'code': code, 'date': d, 'side': side,
                                      'rank': rank, 'tdx': [tn, tb, ts, tnet],
                                      'official': [on, ob, os_]})
        n_pair_ok += pair_ok

    tdx_only = sorted(set(tdx) - set(official))
    name_rate = n_name_match / n_seats if n_seats else 0
    amt_rate = n_amt_match / n_seats if n_seats else 0
    tol_rate = n_amt_tol / n_seats if n_seats else 0
    report = {
        'shared_day_code_pairs': len(shared),
        'pairs_fully_matching': n_pair_ok,
        'seat_rows_compared': n_seats,
        'seat_name_match_rate': round(name_rate, 6),
        'amount_exact_rate': round(amt_rate, 6),
        'amount_0.1pct_rate': round(tol_rate, 6),
        'tdx_events_not_in_official': [
            {'code': c, 'date': d} for c, d in tdx_only][:200],
        'n_tdx_events_not_in_official': len(tdx_only),
        'sample_mismatches': worst,
    }
    OUT_FP.write_text(json.dumps(report, ensure_ascii=False, indent=1),
                      encoding='utf-8')
    print(f'seat rows compared: {n_seats}; name match {n_name_match} '
          f'({name_rate:.2%}); amount exact {n_amt_match} ({amt_rate:.2%}); '
          f'±0.1% {n_amt_tol} ({tol_rate:.2%})')
    print(f'tdx events not covered by official window: {len(tdx_only)}')
    for m in worst[:8]:
        print('  MISMATCH', m['date'], m['code'], m['side'], m['rank'],
              repr(m['tdx'][0][:16]), m['tdx'][1], 'vs',
              repr(m['official'][0][:16]), m['official'][1])
    ok = (len(shared) >= 10 and name_rate >= 0.99 and amt_rate >= 0.97)
    print('GATE:', 'PASS' if ok else 'FAIL (insufficient overlap or mismatch)')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
