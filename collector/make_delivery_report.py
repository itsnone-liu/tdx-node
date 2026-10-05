#!/usr/bin/env python3
"""Refresh docs/DELIVERY.md placeholder numbers from finished datasets.
Run at the very end of the chain (after normalize + gate)."""
import csv
import json
from pathlib import Path

NODE = Path(r'D:\tdx-node')
DOC = NODE / 'docs' / 'DELIVERY.md'


def count_csv(fp: Path):
    with fp.open(encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    days = len({r['trade_date'] for r in rows})
    return len(rows), days


def main():
    repl = {}
    fp = NODE / 'lhb' / 'csv' / 'lhb_seats.csv'
    if fp.exists():
        n, d = count_csv(fp)
        repl['__LHB_ROWS__'] = f'{n:,}'
        repl['__LHB_DAYS__'] = str(d)
    fp = NODE / 'blockmargin' / 'csv' / 'block_trades.csv'
    if fp.exists():
        n, d = count_csv(fp)
        repl['__BLOCK_ROWS__'] = f'{n:,}'
        repl['__BLOCK_DAYS__'] = str(d)
    fp = NODE / 'blockmargin' / 'csv' / 'margin_daily.csv'
    if fp.exists():
        n, d = count_csv(fp)
        repl['__MARGIN_ROWS__'] = f'{n:,}'
        repl['__MARGIN_DAYS__'] = str(d)
    gate_fp = NODE / 'lhb' / 'crosscheck_report.json'
    if gate_fp.exists():
        rep = json.loads(gate_fp.read_text(encoding='utf-8'))
        verdict = rep.get('verdict') or rep.get('result') or 'see report'
        repl['__GATE__'] = str(verdict)
    text = DOC.read_text(encoding='utf-8')
    for k, v in repl.items():
        text = text.replace(k, v)
    DOC.write_text(text, encoding='utf-8')
    print('DELIVERY.md refreshed:', repl)


if __name__ == '__main__':
    main()
