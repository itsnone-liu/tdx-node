"""Live-test SZSE block trade (1932_dzjyzqjy_after) and margin (1837_xxpl)
catalogs: page 1 with a recent date, dump metadata + fields + first rows."""
import json
import sys
import urllib.parse
import urllib.request

H = {'Referer': 'https://www.szse.cn/disclosure/',
     'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                   'AppleWebKit/537.36 Chrome/124.0 Safari/537.36'}
API = 'https://www.szse.cn/api/report/ShowReport/data'


def call(catalog, extra):
    params = {'SHOWTYPE': 'JSON', 'CATALOGID': catalog, 'PAGENO': '1',
              'random': '0.1'}
    params.update(extra)
    url = API + '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=H)
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode('utf-8'))


def show(tag, obj):
    for cat in obj:
        md = cat.get('metadata', {})
        rows = cat.get('data') or []
        print(f'=== {tag} tabkey={md.get("tabkey")} rows={len(rows)} '
              f'pagecount={md.get("pagecount")}')
        if rows:
            print('   fields:', list(rows[0].keys()))
            for r in rows[:3]:
                print('   ', json.dumps(r, ensure_ascii=False)[:220])


def main():
    show('block 2026-09-30',
         call('1932_dzjyzqjy_after',
              {'txtStart': '2026-09-30', 'txtEnd': '2026-09-30', 'TABKEY': 'tab1'}))
    show('block 2021-01-05',
         call('1932_dzjyzqjy_after',
              {'txtStart': '2021-01-05', 'txtEnd': '2021-01-05', 'TABKEY': 'tab1'}))
    show('margin 2026-09-30',
         call('1837_xxpl',
              {'txtStart': '2026-09-30', 'txtEnd': '2026-09-30', 'TABKEY': 'tab1'}))
    show('margin 2021-01-05',
         call('1837_xxpl',
              {'txtStart': '2021-01-05', 'txtEnd': '2021-01-05', 'TABKEY': 'tab1'}))


if __name__ == '__main__':
    main()
