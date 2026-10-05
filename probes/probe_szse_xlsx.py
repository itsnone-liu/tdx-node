#!/usr/bin/env python3
"""Probe SZSE ShowReport xlsx export variants (ONE request each, total <=4).

MUST run only in an SZSE-idle window (no backfill running) — see
LHB_PIPELINE.md. Writes verdict to blockmargin/xlsx_probe.json so
block_margin_backfill.py can pick the working variant automatically.

Variants tried (Referer https://www.szse.cn/):
  A: /api/report/ShowReport/data?SHOWTYPE=XLSX&...   (metadata hint)
  B: SHOWTYPE=EXCEL
  C: /api/report/ShowReport/export?SHOWTYPE=XLSX&...
"""
from __future__ import annotations
import io
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path(r'D:\tdx-node\blockmargin\xlsx_probe.json')
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0'
BASE = 'https://www.szse.cn/api/report/ShowReport/'
DAY = '2026-09-30'


def try_variant(name: str, url: str, params: dict):
    full = url + '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(full, headers={
        'User-Agent': UA, 'Referer': 'https://www.szse.cn/'})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            ct = r.headers.get('Content-Type', '')
            raw = r.read()
        ok_ct = 'json' not in ct.lower()
        result = {'name': name, 'http': 'ok', 'content_type': ct,
                  'bytes': len(raw), 'secs': round(time.time() - t0, 1),
                  'binary': ok_ct and len(raw) > 200}
        if ok_ct and raw[:2] == b'PK':
            result['xlsx'] = True
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(max_row=3, values_only=True))
            result['sheet'] = ws.title
            result['first_rows'] = [[str(c)[:24] if c is not None else ''
                                     for c in r] for r in rows]
        else:
            result['xlsx'] = False
            result['head'] = raw[:200].decode('utf-8', errors='replace')
        return result
    except Exception as exc:  # noqa: BLE001
        return {'name': name, 'http': 'fail', 'error': repr(exc)[:200],
                'secs': round(time.time() - t0, 1)}


def main():
    common = {'SHOWTYPE': 'XLSX', 'CATALOGID': '1837_xxpl', 'TABKEY': 'tab2',
              'txtDate': DAY, 'random': '0.42'}
    results = [
        try_variant('data?SHOWTYPE=XLSX', BASE + 'data', common),
    ]
    time.sleep(1.0)
    c2 = dict(common, SHOWTYPE='EXCEL')
    results.append(try_variant('data?SHOWTYPE=EXCEL', BASE + 'data', c2))
    time.sleep(1.0)
    results.append(try_variant('export?SHOWTYPE=XLSX', BASE + 'export', common))
    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=1),
                   encoding='utf-8')
    winner = next((r['name'] for r in results if r.get('xlsx')), None)
    print(json.dumps(results, ensure_ascii=False, indent=1))
    print('WINNER:', winner or 'NONE — JSON pagination fallback stays')


if __name__ == '__main__':
    main()
