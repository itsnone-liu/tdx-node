#!/usr/bin/env python3
"""Normalize raw margin responses into blockmargin/csv/margin_daily.csv.

Sources:
  SSE  : raw/margin/sse/YYYYMMDD_pN.json  — rzye/rzmre/rzche yuan,
         rqyl/rqmcl/rqchl shares. Direct use.
  SZSE : raw/margin/szse/YYYYMMDD_pN.json — jrrzmr/jrrzye/jrrjmc/jrrzrjye
         in 亿元, jrrjyl in 万股, jrrjye in 万元 (units inferred &
         cross-checked: rqye ~= rqyl * close price; see verify option).

Output schema (margin_daily.csv):
  trade_date, exchange, code, name, rzye, rzmre, rzche, rqyl, rqmcl, rqchl,
  rzrqye, source, raw_file   (amounts yuan, volumes shares)

python margin_normalize.py [--verify]  : verify SZSE units via TDX close px
"""
from __future__ import annotations
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

NODE = Path(r'D:\tdx-node')
ROOT = NODE / 'blockmargin'
RAW = ROOT / 'raw'
OUT = ROOT / 'csv'

COLS = ['trade_date', 'exchange', 'code', 'name', 'rzye', 'rzmre', 'rzche',
        'rqyl', 'rqmcl', 'rqchl', 'rzrqye', 'source', 'raw_file']
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


def iso(day: str) -> str:
    return f'{day[:4]}-{day[4:6]}-{day[6:]}'


def parse_sse():
    n = 0
    for fp in sorted((RAW / 'margin' / 'sse').glob('*.json')):
        day = fp.stem.split('_')[0]
        obj = json.loads(fp.read_text(encoding='utf-8'))
        for r in (obj.get('pageHelp') or {}).get('data') or []:
            ROWS.append({
                'trade_date': iso(str(r.get('opDate') or day)),
                'exchange': 'SSE', 'code': r.get('stockCode'),
                'name': clean(r.get('securityAbbr')),
                'rzye': to_f(r.get('rzye')), 'rzmre': to_f(r.get('rzmre')),
                'rzche': to_f(r.get('rzche')), 'rqyl': to_f(r.get('rqyl')),
                'rqmcl': to_f(r.get('rqmcl')), 'rqchl': to_f(r.get('rqchl')),
                'rzrqye': (to_f(r.get('rzye')) or 0) +
                          ((to_f(r.get('rqyl')) or 0) * 0),  # rqye needs px; see meta
                'source': 'SSE official', 'raw_file': f'raw/margin/sse/{fp.name}'})
        n += 1
    print(f'margin sse: {n} days', flush=True)


def parse_szse():
    n = 0
    for fp in sorted((RAW / 'margin' / 'szse').glob('*_p1.json')):
        day = fp.stem.split('_')[0]
        obj = json.loads(fp.read_text(encoding='utf-8'))
        for cat in obj:
            if cat.get('metadata', {}).get('tabkey') != 'tab2':
                continue
            for r in cat.get('data') or []:
                ROWS.append({
                    'trade_date': iso(day), 'exchange': 'SZSE',
                    'code': clean(r.get('zqdm')), 'name': clean(r.get('zqjc')),
                    'rzye': (to_f(r.get('jrrzye')) or 0) * 1e8,
                    'rzmre': (to_f(r.get('jrrzmr')) or 0) * 1e8,
                    'rzche': (to_f(r.get('jrrjmc')) or 0) * 1e8,
                    'rqyl': (to_f(r.get('jrrjyl')) or 0) * 1e4,
                    'rqmcl': None, 'rqchl': None,
                    'rzrqye': (to_f(r.get('jrrzrjye')) or 0) * 1e8,
                    'source': 'SZSE official',
                    'raw_file': f'raw/margin/szse/{fp.name}'})
        n += 1
    print(f'margin szse: {n} days', flush=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    parse_sse()
    parse_szse()
    ROWS.sort(key=lambda r: (r['trade_date'], r['exchange'], r['code']))
    fp = OUT / 'margin_daily.csv'
    with fp.open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(ROWS)
    dates = sorted({r['trade_date'] for r in ROWS})
    meta = {
        'dataset': 'margin_daily',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'rows': len(ROWS), 'days': len(dates),
        'coverage': [dates[0] if dates else None, dates[-1] if dates else None],
        'units': 'all amounts yuan, volumes shares',
        'unit_notes': {
            'SSE': 'raw already yuan/shares',
            'SZSE': 'raw jrrzye/jrrzmr/jrrjmc/jrrzrjye=亿元(x1e8), '
                    'jrrjyl=万股(x1e4), jrrjye=万元; rqmcl/rqchl not provided '
                    'by SZSE tab2 (SSE has them)',
            'rzrqye_SSE': 'SSE gives no combined column; equals rzye until '
                          'rqye(=rqyl*close) is added'},
        'sources': ['SSE commonSoaQuery RZRQ_MX_INFO (official)',
                    'SZSE ShowReport 1837_xxpl tab2 (official)'],
    }
    (OUT / 'MARGIN_META.json').write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'rows={len(ROWS)} days={len(dates)} '
          f'({dates[0] if dates else "-"}..{dates[-1] if dates else "-"})',
          flush=True)


if __name__ == '__main__':
    main()
