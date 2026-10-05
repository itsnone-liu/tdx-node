"""Probe SZSE LHB seat-detail API (CATALOGID=1842_detal).

From the daily row's bz link:
  /ShowReport/data?SHOWTYPE=JSON&CATALOGID=1842_detal&TABKEY=tab1,tab2
      &DQRQ=2026-09-30&ZQDM=000002&ZBDM=0902
tab1 expected = buy seats, tab2 = sell seats.
"""
import json
import urllib.request
import urllib.parse

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0 Safari/537.36')


def fetch_detail(dqrq, zqdm, zbdm):
    tabkey = urllib.parse.quote('tab1,tab2', safe='')
    url = (f'https://www.szse.cn/api/report/ShowReport/data?SHOWTYPE=JSON'
           f'&CATALOGID=1842_detal&TABKEY={tabkey}&DQRQ={dqrq}&ZQDM={zqdm}&ZBDM={zbdm}'
           f'&random=0.77')
    req = urllib.request.Request(url, headers={'User-Agent': UA,
                                                'Referer': 'https://www.szse.cn/'})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode('utf-8'))


def main():
    for dqrq, zqdm, zbdm in [
        ('2026-09-30', '000002', '0902'),
        ('2021-01-08', '000007', '0901'),
    ]:
        try:
            obj = fetch_detail(dqrq, zqdm, zbdm)
            print(f'=== {dqrq} {zqdm} ZBDM={zbdm}: {len(obj)} catalog objects')
            for cat in obj:
                md = cat['metadata']
                rows = cat.get('data', [])
                print(f'  [{md.get("name")}] tabkey={md.get("tabkey")} rows={len(rows)}')
                if rows:
                    print('    fields:', list(rows[0].keys()))
                    for rw in rows[:3]:
                        print('    ', json.dumps(rw, ensure_ascii=False)[:300])
        except Exception as exc:
            print(f'=== {dqrq} {zqdm} EXC {exc!r}')


if __name__ == '__main__':
    main()
