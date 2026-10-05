"""Probe SZSE LHB API (ShowReport/data, CATALOGID=1842_xxpl_after).

Goals:
1. right date-filter params (txtStart/txtEnd vs txtQueryDate)
2. field schema of data rows
3. can PAGESIZE be raised? (pagesize=10 default)
4. does history go back to 2021?
"""
import json
import time
import urllib.request

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0 Safari/537.36')
BASE = 'https://www.szse.cn/api/report/ShowReport/data'
CAT = '1842_xxpl_after'


def fetch(params):
    qs = '&'.join(f'{k}={v}' for k, v in params.items())
    url = f'{BASE}?SHOWTYPE=JSON&CATALOGID={CAT}&{qs}'
    req = urllib.request.Request(url, headers={'User-Agent': UA,
                                                'Referer': 'https://www.szse.cn/'})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode('utf-8'))


def show(tag, obj):
    md = obj[0]['metadata']
    rows = obj[0].get('data', [])
    print(f'--- {tag}: recordcount={md.get("recordcount")} pagesize={md.get("pagesize")} '
          f'pageno={md.get("pageno")} pagecount={md.get("pagecount")} rows={len(rows)}')
    if rows:
        print('    fields:', list(rows[0].keys()))
        print('    sample:', json.dumps(rows[0], ensure_ascii=False)[:400])
    return md, rows


def main():
    # 1) default page (no date filter)
    md, rows = show('no-filter', fetch({'TABKEY': 'tab1', 'random': '0.1'}))

    # 2) try date filters on a known trading day 2026-09-30
    for params in [
        {'TABKEY': 'tab1', 'txtQueryDate': '2026-09-30', 'random': '0.2'},
        {'TABKEY': 'tab1', 'txtStart': '2026-09-30', 'txtEnd': '2026-09-30', 'random': '0.3'},
        {'TABKEY': 'tab1', 'txtStart': '20260930', 'txtEnd': '20260930', 'random': '0.4'},
    ]:
        try:
            show(str(params), fetch(params))
        except Exception as exc:
            print(f'--- {params} EXC {exc!r}')
        time.sleep(1)

    # 3) pagesize raise attempt
    try:
        show('pagesize=200', fetch({'TABKEY': 'tab1', 'txtStart': '2026-09-30',
                                    'txtEnd': '2026-09-30', 'PAGESIZE': '200',
                                    'random': '0.5'}))
    except Exception as exc:
        print(f'--- PAGESIZE EXC {exc!r}')

    # 4) history depth: 2021-01-05 (first trading week of 2021)
    try:
        show('2021-01-05..08', fetch({'TABKEY': 'tab1', 'txtStart': '2021-01-05',
                                      'txtEnd': '2021-01-08', 'PAGESIZE': '50',
                                      'random': '0.6'}))
    except Exception as exc:
        print(f'--- 2021 EXC {exc!r}')


if __name__ == '__main__':
    main()
