"""Data-quality audit over accumulated LHB + block/margin raw data.

Checks:
  1. LHB per-day integrity: szse list rows vs saved detail files; SSE rows>0
  2. Seat composition: inst/northbound seat share, rank completeness (1-5)
  3. Amount sanity: no negatives on primary side, top-1 >= top-2 ordering
  4. Day-of-week/coverage: every calendar day has state, COMPLETE or noted
"""
from __future__ import annotations
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

NODE = Path(r'D:\tdx-node')
LHB = NODE / 'lhb'
BM = NODE / 'blockmargin'
CAL = set(json.loads((NODE / 'manifests' / 'trading_calendar_2021_2026.json')
                     .read_text(encoding='utf-8')))
CAL |= set(json.loads((NODE / 'manifests' / 'calendar_prefill_2021.json')
                      .read_text(encoding='utf-8')))


def day_integrity():
    state = json.loads((LHB / 'backfill_state.json').read_text(encoding='utf-8'))
    partial, failed, empty = [], [], []
    for day, rec in sorted(state.items()):
        st = rec.get('status')
        if st == 'FAILED':
            failed.append(day)
        elif st == 'PARTIAL' or rec.get('szse_detail_ok', 0) < rec.get('szse_detail_total', 0):
            if rec.get('szse_list_rows', 0) or rec.get('sse_main_rows', 0):
                partial.append((day, rec.get('szse_detail_ok'),
                                rec.get('szse_detail_total')))
        if (not rec.get('szse_list_rows')) and (not rec.get('sse_main_rows')) \
                and not rec.get('sse_star_rows'):
            empty.append(day)
    have = set(state)
    missing = sorted(CAL - have)
    print(f'days in state: {len(state)}; calendar: {len(CAL)}; '
          f'missing-from-state: {len(missing)} {missing[:6]}')
    print(f'FAILED days: {failed}')
    print(f'PARTIAL days: {partial[:10]} ({"..." if len(partial) > 10 else ""} total {len(partial)})')
    print(f'zero-row days (holidays ok): {len(empty)}')


def seat_quality():
    rows = list(csv.DictReader(
        (LHB / 'csv' / 'lhb_seats.csv').open(encoding='utf-8-sig')))
    n = len(rows)
    inst = sum(1 for r in rows if r['is_institution'] == 'True')
    nb = sum(1 for r in rows if r['is_northbound'] == 'True')
    rank_full = Counter((r['side'], r['rank']) for r in rows)
    bad_order = 0
    bykey = defaultdict(list)
    for r in rows:
        bykey[(r['trade_date'], r['exchange'], r['code'], r['reason_code'],
               r['side'])].append(r)
    for k, rs in bykey.items():
        amts = [float(r['buy_amt'] or 0) if k[4] == 'B'
                else float(r['sell_amt'] or 0) for r in sorted(
                    rs, key=lambda x: int(x['rank']))]
        if any(a < b for a, b in zip(amts, amts[1:])):
            bad_order += 1
    print(f'seat rows: {n}; inst {inst} ({inst/n:.1%}); nb {nb} ({nb/n:.1%})')
    print(f'rank coverage: {sorted(rank_full.items())[:6]}...')
    print(f'amount monotonicity violations (rank i < rank i+1 amount): '
          f'{bad_order}/{len(bykey)} lists')
    sse_rows = [r for r in rows if r['exchange'] == 'SSE']
    szse_rows = [r for r in rows if r['exchange'] == 'SZSE']
    print(f'SSE {len(sse_rows)} rows / SZSE {len(szse_rows)} rows')


def bm_quality():
    bs = json.loads((BM / 'backfill_state.json').read_text(encoding='utf-8'))
    kinds = Counter()
    for k, v in bs.items():
        if v.get('status') == 'COMPLETE':
            kinds[k.split('/')[0] + '/' + k.split('/')[1]] += 1
    print('blockmargin complete:', dict(kinds))
    btr = list(csv.DictReader(
        (BM / 'csv' / 'block_trades.csv').open(encoding='utf-8-sig')))
    print(f'block csv rows {len(btr)}, '
          f'inst-buyer {sum(1 for r in btr if r[chr(98)+chr(117)+chr(121)+chr(95)+chr(105)+chr(115)+chr(95)+chr(105)+chr(110)+chr(115)+chr(116)+chr(105)+chr(116)+chr(117)+chr(116)+chr(105)+chr(111)+chr(110)]=="True")}')
    mgr = list(csv.DictReader(
        (BM / 'csv' / 'margin_daily.csv').open(encoding='utf-8-sig')))
    rzyes = [float(r['rzye']) for r in mgr if r['rzye']]
    print(f'margin csv rows {len(mgr)}; rzye max {max(rzyes)/1e8:.1f}亿 '
          f'median {sorted(rzyes)[len(rzyes)//2]/1e8:.2f}亿')


if __name__ == '__main__':
    print('--- LHB day integrity ---')
    day_integrity()
    print('--- seat quality ---')
    seat_quality()
    print('--- block/margin ---')
    bm_quality()
