"""External spot-check: eastmoney LHB detail for 000007 2021-02-22 vs our CSV.
Vendor site (not SZSE) — safe during backfill."""
import csv
import json
import urllib.parse
import urllib.request

URL = ('https://datacenter-web.eastmoney.com/api/data/v1/get?'
       + urllib.parse.urlencode({
           'reportName': 'RPT_DAILYBILLBOARD_DETAILSNEW',
           'columns': 'ALL',
           'filter': '(TRADE_DATE=\'2021-02-22\')(SECURITY_CODE="000007")',
           'pageSize': '50', 'pageNumber': '1', 'sortTypes': '-1,1',
           'sortColumns': 'BILLBOARD_NET_AMT,SECURITY_CODE',
           'source': 'WEB', 'client': 'WEB'}))


def main():
    req = urllib.request.Request(URL, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0',
        'Referer': 'https://data.eastmoney.com/'})
    with urllib.request.urlopen(req, timeout=25) as r:
        obj = json.loads(r.read().decode('utf-8'))
    rows = ((obj.get('result') or {}).get('data')) or []
    print(f'EM rows: {len(rows)}')
    if rows:
        r0 = rows[0]
        print('fields sample:', [k for k in r0.keys()][:18])
    ours = [r for r in csv.DictReader(
        open(r'D:\tdx-node\lhb\csv\lhb_seats.csv', encoding='utf-8-sig'))
        if r['trade_date'] == '2021-02-22' and r['code'] == '000007']
    for r in rows:
        print(json.dumps({k: r.get(k) for k in (
            'TRADE_DATE', 'SECURITY_CODE', 'EXPLANATION', 'CLOSE_PRICE',
            'BILLBOARD_BUY_AMT', 'BILLBOARD_SELL_AMT')},
            ensure_ascii=False)[:300])
    print('--- our aggregate:')
    for r in csv.DictReader(
            open(r'D:\tdx-node\lhb\csv\lhb_daily_stock.csv',
                 encoding='utf-8-sig')):
        if r['trade_date'] == '2021-02-22' and r['code'] == '000007':
            print(json.dumps(r, ensure_ascii=False)[:400])


if __name__ == '__main__':
    main()
