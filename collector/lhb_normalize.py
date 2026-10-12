#!/usr/bin/env python3
"""Normalize raw LHB responses (lhb/raw/**) into the unified seat-level CSV.

Output (lhb/csv/):
  lhb_seats.csv         one row per (date, stock, reason, side, rank) seat
  lhb_daily_stock.csv   day x stock x reason aggregates (inst/northbound nets)
  DATASET_META.json     schema + sources + coverage + known gaps

All monetary amounts are normalized to yuan (SSE STAR source is 万元, x10000).
Run any time — it processes whatever raw days exist (partial-safe).
"""
from __future__ import annotations
import csv
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

NODE = Path(r'D:\tdx-node')
RAW = NODE / 'lhb' / 'raw'
OUT = NODE / 'lhb' / 'csv'
STATE_FP = NODE / 'lhb' / 'backfill_state.json'
REFTYPE_FP = NODE / 'manifests' / 'sse_reftype_map.json'

SEAT_COLS = ['trade_date', 'exchange', 'board', 'code', 'name', 'reason_code',
             'reason_text', 'side', 'rank', 'seat_name', 'is_institution',
             'is_northbound', 'buy_amt', 'sell_amt', 'abnormal_start',
             'abnormal_end', 'source', 'raw_file', 'available_at']
AGG_COLS = ['trade_date', 'exchange', 'board', 'code', 'name', 'reason_code',
            'reason_text', 'n_buy_seats', 'n_sell_seats', 'buy_amt', 'sell_amt',
            'net_amt', 'inst_buy', 'inst_sell', 'inst_net', 'nb_buy', 'nb_sell',
            'nb_net', 'source', 'available_at']

NB_PAT = re.compile(r'(沪股通专用|深股通专用|机构专用)')


def clean_name(s):
    return (s or '').replace('&nbsp;', ' ').strip()


def to_f(s):
    if s is None or s == '':
        return None
    try:
        return float(str(s).replace(',', ''))
    except ValueError:
        return None


def split_list(s):
    return [clean_name(x) for x in (s or '').split(',') if x.strip()] if s else []


def classify_seat(name: str):
    inst = '机构专用' in name
    nb = ('沪股通专用' in name) or ('深股通专用' in name)
    return inst, nb


SEAT_ROWS: list[dict] = []
seen_keys = set()
dup_count = 0


def emit(trade_date, exchange, board, code, name, reason_code, reason_text,
         side, rank, seat_name, buy_amt, sell_amt, ab_start, ab_end, source,
         raw_file):
    global dup_count
    key = (trade_date, exchange, code, reason_code, side, rank)
    if key in seen_keys:
        dup_count += 1
        return
    seen_keys.add(key)
    inst, nb = classify_seat(seat_name)
    SEAT_ROWS.append({
        'trade_date': trade_date, 'exchange': exchange, 'board': board,
        'code': code, 'name': name, 'reason_code': reason_code,
        'reason_text': reason_text, 'side': side, 'rank': rank,
        'seat_name': seat_name, 'is_institution': inst, 'is_northbound': nb,
        'buy_amt': buy_amt, 'sell_amt': sell_amt,
        'abnormal_start': ab_start, 'abnormal_end': ab_end,
        'source': source, 'raw_file': raw_file,
    })


def parse_sse_main():
    reftype = json.loads(REFTYPE_FP.read_text(encoding='utf-8'))
    n_files = 0
    for fp in sorted((RAW / 'sse_main').glob('*.json')):
        day = fp.stem
        iso = f'{day[:4]}-{day[4:6]}-{day[6:]}'
        obj = json.loads(fp.read_text(encoding='utf-8'))
        rows = (obj.get('pageHelp') or {}).get('data') or []
        done_pairs = set()
        for r in rows:
            code, rtc = r.get('secCode'), r.get('refType')
            if (code, rtc) in done_pairs:
                continue  # B/S rows duplicate the same seat lists
            done_pairs.add((code, rtc))
            name = clean_name(r.get('secAbbr'))
            reason_text = reftype.get(str(rtc), '')
            board = 'STAR' if str(code).startswith('68') else 'MAIN'
            for side, names_f, amt_f in (
                    ('B', 'branchNameB', 'branchTxAmtB'),
                    ('S', 'branchNameS', 'branchTxAmtS')):
                names = split_list(r.get(names_f))
                amts = split_list(r.get(amt_f))
                for i, (sn, sa) in enumerate(zip(names, amts), 1):
                    amt = to_f(sa)
                    emit(iso, 'SSE', board, code, name, rtc, reason_text,
                         side, i, sn,
                         amt if side == 'B' else None,
                         amt if side == 'S' else None,
                         r.get('abnormalStart'), r.get('abnormalEnd'),
                         'SSE official', f'raw/sse_main/{fp.name}')
        n_files += 1
    print(f'sse_main: {n_files} days', flush=True)


def parse_sse_star():
    reftype = json.loads(REFTYPE_FP.read_text(encoding='utf-8'))
    n_files = 0
    for fp in sorted((RAW / 'sse_star').glob('*.json')):
        day = fp.stem
        iso = f'{day[:4]}-{day[4:6]}-{day[6:]}'
        obj = json.loads(fp.read_text(encoding='utf-8'))
        rows = (obj.get('pageHelp') or {}).get('data') or []
        done_pairs = set()
        for r in rows:
            code, rtc, direct = r.get('secCode'), r.get('refType'), r.get('txDirect')
            if (code, rtc, direct) in done_pairs:
                continue
            done_pairs.add((code, rtc, direct))
            name = clean_name(r.get('secAbbr'))
            reason_text = reftype.get(str(rtc), '')
            side = 'B' if direct == 'B' else 'S'
            names_f = 'deptNameB' if side == 'B' else 'deptNameS'
            amt_f = 'deptTxAmtB' if side == 'B' else 'deptTxAmtS'
            names = split_list(r.get(names_f))
            amts = split_list(r.get(amt_f))
            for i, (sn, sa) in enumerate(zip(names, amts), 1):
                amt = to_f(sa)
                if amt is not None:
                    amt *= 10000.0  # 万元 -> 元
                emit(iso, 'SSE', 'STAR', code, name, rtc, reason_text,
                     side, i, sn,
                     amt if side == 'B' else None,
                     amt if side == 'S' else None,
                     r.get('unnormalStartDate'), r.get('unnormalEndDate'),
                     'SSE official', f'raw/sse_star/{fp.name}')
        n_files += 1
    print(f'sse_star: {n_files} days', flush=True)


MMLB_RE = re.compile(r'^(买|卖)\s*(\d+)$')


def parse_szse():
    n_days = n_details = 0
    for fp in sorted((RAW / 'szse_list').glob('*_p1.json')):
        day = fp.stem.split('_')[0]
        iso = f'{day[:4]}-{day[4:6]}-{day[6:]}'
        # collect (zqdm -> plyy, zbdm) from all pages of this day
        day_meta = {}
        for pg in sorted((RAW / 'szse_list').glob(f'{day}_p*.json')):
            obj = json.loads(pg.read_text(encoding='utf-8'))
            for r in obj[0].get('data') or []:
                m = re.search(r'DQRQ=([\d-]+)&ZQDM=(\d+)&ZBDM=(\d+)',
                              r.get('bz') or '')
                if m:
                    day_meta[(m.group(2), m.group(3))] = (
                        clean_name(r.get('zqjc')), clean_name(r.get('plyy')))
        for (zqdm, zbdm), (name, plyy) in day_meta.items():
            dfp = RAW / 'szse_detail' / f'{day}_{zqdm}_{zbdm}.json'
            if not dfp.exists():
                continue
            dobj = json.loads(dfp.read_text(encoding='utf-8'))
            header = {}
            for cat in dobj:
                if cat.get('metadata', {}).get('tabkey') == 'tab1':
                    header = (cat.get('data') or [{}])[0]
                elif cat.get('metadata', {}).get('tabkey') == 'tab2':
                    for seat in cat.get('data') or []:
                        m = MMLB_RE.match(clean_name(seat.get('mmlb')))
                        if not m:
                            continue
                        side = m.group(1).replace('买', 'B').replace('卖', 'S')
                        rank = int(m.group(2))
                        sn = clean_name(seat.get('zsmc'))
                        # SZSE tab2 seats carry BOTH mrje and mcje — keep both
                        # (a 买N seat can have a nonzero sell leg and vice versa)
                        emit(iso, 'SZSE', 'MAIN', zqdm, name, zbdm, plyy,
                             side, rank, sn,
                             to_f(seat.get('mrje')) or 0.0,
                             to_f(seat.get('mcje')) or 0.0,
                             None, None, 'SZSE official',
                             f'raw/szse_detail/{dfp.name}')
                    n_details += 1
        n_days += 1
    print(f'szse: {n_days} days, {n_details} details', flush=True)


def aggregate():
    agg = defaultdict(lambda: {
        'n_buy_seats': 0, 'n_sell_seats': 0, 'buy_amt': 0.0, 'sell_amt': 0.0,
        'inst_buy': 0.0, 'inst_sell': 0.0, 'nb_buy': 0.0, 'nb_sell': 0.0})
    info = {}
    for r in SEAT_ROWS:
        k = (r['trade_date'], r['exchange'], r['code'], r['reason_code'])
        a = agg[k]
        info[k] = (r['name'], r['reason_text'], r['board'], r['source'])
        if r['side'] == 'B':
            a['n_buy_seats'] += 1
            a['buy_amt'] += r['buy_amt'] or 0.0
            if r['is_institution']:
                a['inst_buy'] += r['buy_amt'] or 0.0
            if r['is_northbound']:
                a['nb_buy'] += r['buy_amt'] or 0.0
        else:
            a['n_sell_seats'] += 1
            a['sell_amt'] += r['sell_amt'] or 0.0
            if r['is_institution']:
                a['inst_sell'] += r['sell_amt'] or 0.0
            if r['is_northbound']:
                a['nb_sell'] += r['sell_amt'] or 0.0
    rows = []
    for (d, ex, code, rtc), a in agg.items():
        name, reason_text, board, source = info[(d, ex, code, rtc)]
        rows.append({
            'trade_date': d, 'exchange': ex, 'board': board, 'code': code,
            'name': name, 'reason_code': rtc, 'reason_text': reason_text,
            **a, 'net_amt': a['buy_amt'] - a['sell_amt'],
            'inst_net': a['inst_buy'] - a['inst_sell'],
            'nb_net': a['nb_buy'] - a['nb_sell'], 'source': source})
    rows.sort(key=lambda r: (r['trade_date'], r['exchange'], r['code'],
                             str(r['reason_code'])))
    return rows


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    parse_sse_main()
    parse_sse_star()
    parse_szse()
    SEAT_ROWS.sort(key=lambda r: (r['trade_date'], r['exchange'], r['code'],
                                  str(r['reason_code']), r['side'], r['rank']))
    import sys as _s, os as _o
    _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__)))
    import pit
    pit.stamp(SEAT_ROWS, 'lhb')

    seats_fp = OUT / 'lhb_seats.csv'
    with seats_fp.open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=SEAT_COLS)
        w.writeheader()
        w.writerows(SEAT_ROWS)

    agg_rows = aggregate()
    pit.stamp(agg_rows, 'lhb')
    agg_fp = OUT / 'lhb_daily_stock.csv'
    with agg_fp.open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=AGG_COLS)
        w.writeheader()
        w.writerows(agg_rows)

    state = json.loads(STATE_FP.read_text(encoding='utf-8')) if STATE_FP.exists() else {}
    failed = sorted(d for d, v in state.items() if v.get('status') != 'COMPLETE')
    dates = sorted({r['trade_date'] for r in SEAT_ROWS})
    meta = {
        'dataset': 'lhb_seats / lhb_daily_stock',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'coverage': {'first_date': dates[0] if dates else None,
                     'last_date': dates[-1] if dates else None,
                     'n_days_with_rows': len(dates),
                     'n_seat_rows': len(SEAT_ROWS),
                     'n_day_stock_rows': len(agg_rows),
                     'deduped_duplicate_seat_rows': dup_count},
        'schema': {
            'trade_date': 'YYYY-MM-DD (disclosure/trade date)',
            'code': '6-digit exchange code, leading zeros preserved',
            'board': 'MAIN / STAR',
            'reason_code': 'SSE refType / SZSE ZBDM',
            'side': 'B=buy-side seat ranking, S=sell-side',
            'rank': '1..5 within side',
            'is_institution': "seat_name contains '机构专用'",
            'is_northbound': "seat_name contains 沪股通专用/深股通专用",
            'buy_amt/sell_amt': 'yuan; the amount booked to that seat on that side',
            'note': 'SSE STAR source amounts are 万元 in raw, x10000 here; '
                    'SZSE detail amounts are yuan in raw'},
        'sources': {
            'SSE': 'query.sse.com.cn/marketdata/tradedata/queryAllTradeOpenDate.do '
                   '(main) + queryKCBTradeInfo.do (STAR) — official',
            'SZSE': 'szse.cn/api/report/ShowReport/data CATALOGID=1842_xxpl_after '
                    '(daily list) + 1842_detal (seat detail) — official'},
        'failed_or_incomplete_days': failed,
    }
    (OUT / 'DATASET_META.json').write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'seats={len(SEAT_ROWS)} day_stock={len(agg_rows)} '
          f'dups_dropped={dup_count} days={len(dates)} '
          f'({dates[0] if dates else "-"}..{dates[-1] if dates else "-"})',
          flush=True)
    print(f'wrote {seats_fp} and {agg_fp}', flush=True)


if __name__ == '__main__':
    main()
