#!/usr/bin/env python3
"""Normalize raw block-trade responses into blockmargin/csv/block_trades.csv.

Sources:
  SSE  : blockmargin/raw/block/sse/YYYYMMDD_pN.json  (pageHelp.data rows)
         price yuan, tradeamount 万元, tradeqty 万股/万份 -> normalized
  SZSE : raw/block/szse_list (per-stock daily aggregates)
       + raw/block/szse_detail/YYYYMMDD_<code>.json (per-trade rows:
         cjjg 元, cjgsnew 万股, cjjenew 万元, bxwmc/sxwmc buyer/seller)

Output schema (block_trades.csv):
  trade_date, exchange, code, name, price, volume, amount, buyer, seller,
  buy_is_institution, sell_is_institution, is_special_session, source, raw_file
  price=yuan, volume=shares, amount=yuan.
"""
from __future__ import annotations
import os
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

NODE = Path(os.environ.get('TDX_NODE') or r'D:\tdx-node').expanduser()  # TDX_NODE env → Linux/米线; 默认仍是 Windows D:\tdx-node
ROOT = NODE / 'blockmargin'
RAW = ROOT / 'raw'
OUT = ROOT / 'csv'
STATE_FP = ROOT / 'backfill_state.json'

COLS = ['trade_date', 'exchange', 'code', 'name', 'price', 'volume', 'amount',
        'buyer', 'seller', 'buy_is_institution', 'sell_is_institution',
        'is_special_session', 'source', 'raw_file', 'available_at']
ROWS: list[dict] = []


def to_f(s):
    if s is None or s == '':
        return None
    try:
        return float(str(s).replace(',', ''))
    except ValueError:
        return None


def clean(s):
    return (s or '').replace('&nbsp;', ' ').strip()


def emit(**kw):
    kw['buyer'] = clean(kw.get('buyer'))
    kw['seller'] = clean(kw.get('seller'))
    kw['buy_is_institution'] = '机构专用' in kw['buyer']
    kw['sell_is_institution'] = '机构专用' in kw['seller']
    ROWS.append(kw)


def parse_sse():
    n = 0
    for fp in sorted((RAW / 'block' / 'sse').glob('*.json')):
        day = fp.stem.split('_')[0]
        iso = f'{day[:4]}-{day[4:6]}-{day[6:]}'
        obj = json.loads(fp.read_text(encoding='utf-8'))
        for r in (obj.get('pageHelp') or {}).get('data') or []:
            emit(trade_date=iso, exchange='SSE', code=r.get('stockid'),
                 name=clean(r.get('abbrname')),
                 price=to_f(r.get('tradeprice')),
                 volume=(to_f(r.get('tradeqty')) or 0) * 10000,
                 amount=(to_f(r.get('tradeamount')) or 0) * 10000,
                 buyer=r.get('branchbuy'), seller=r.get('branchsell'),
                 is_special_session=(clean(r.get('ifZc')) == '是'),
                 source='SSE official',
                 raw_file=f'raw/block/sse/{fp.name}')
        n += 1
    print(f'block sse: {n} days', flush=True)


def parse_szse():
    n = 0
    for fp in sorted((RAW / 'block' / 'szse_detail').glob('*.json')):
        day = fp.stem.split('_')[0]
        iso = f'{day[:4]}-{day[4:6]}-{day[6:]}'
        code = fp.stem.split('_')[1]
        obj = json.loads(fp.read_text(encoding='utf-8'))
        for cat in obj:
            if cat.get('metadata', {}).get('tabkey') != 'tab1':
                continue
            for r in cat.get('data') or []:
                dqrq = clean(r.get('cjrq'))
                emit(trade_date=dqrq or iso, exchange='SZSE', code=code,
                     name=clean(r.get('zqjc')),
                     price=to_f(r.get('cjjg')),
                     volume=(to_f(r.get('cjgsnew')) or 0) * 10000,
                     amount=(to_f(r.get('cjjenew')) or 0) * 10000,
                     buyer=r.get('bxwmc'), seller=r.get('sxwmc'),
                     is_special_session=None,
                     source='SZSE official',
                     raw_file=f'raw/block/szse_detail/{fp.name}')
            n += 1
    print(f'block szse details: {n} files', flush=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    parse_sse()
    parse_szse()
    ROWS.sort(key=lambda r: (r['trade_date'], r['exchange'], r['code']))
    import sys as _s, os as _o
    _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__)))
    import pit
    pit.stamp(ROWS, 'block')
    fp = OUT / 'block_trades.csv'
    with fp.open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(ROWS)
    dates = sorted({r['trade_date'] for r in ROWS})
    meta = {
        'dataset': 'block_trades',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'rows': len(ROWS),
        'days': len(dates),
        'coverage': [dates[0] if dates else None, dates[-1] if dates else None],
        'units': 'price yuan / volume shares / amount yuan '
                 '(raw 万元/万股 already converted)',
        'sources': ['SSE commonQuery DZJYXX_L_1 (official)',
                    'SZSE ShowReport 1932 + 1265 (official)'],
    }
    (OUT / 'BLOCK_META.json').write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'rows={len(ROWS)} days={len(dates)} '
          f'({dates[0] if dates else "-"}..{dates[-1] if dates else "-"})',
          flush=True)


if __name__ == '__main__':
    main()
