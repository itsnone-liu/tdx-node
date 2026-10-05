"""Live-test SSE margin endpoints (RZRQ_HZ_INFO aggregate, RZRQ_MX_INFO
per-stock detail) via commonSoaQuery.do with beginDate/endDate + pagination."""
import json
import urllib.parse
import urllib.request

Q = 'http://query.sse.com.cn/commonSoaQuery.do'
H = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                   'Chrome/124.0 Safari/537.36',
     'Referer': 'http://www.sse.com.cn/market/othersdata/margin/detail/'}


def call(sqlid, extra, page=1, size=25):
    params = {
        'isPagination': 'true',
        'pageHelp.pageSize': str(size),
        'pageHelp.pageNo': str(page),
        'pageHelp.beginPage': str(page),
        'pageHelp.cacheSize': '1',
        'pageHelp.endPage': str(page),
        'sqlId': sqlid,
    }
    params.update(extra)
    url = Q + '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=H)
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode('utf-8'))


def show(tag, obj):
    ph = obj.get('pageHelp') or {}
    rows = ph.get('data') or []
    print(f'=== {tag}: rows={len(rows)} total={ph.get("total")}')
    if rows:
        print('   fields:', list(rows[0].keys()))
        for r in rows[:3]:
            print('   ', json.dumps(r, ensure_ascii=False)[:260])


def main():
    show('MX per-stock 2021-01-05 p1',
         call('RZRQ_MX_INFO', {'beginDate': '2021-01-05', 'endDate': '2021-01-05'}))
    show('MX per-stock 2026-09-30 p1 size100',
         call('RZRQ_MX_INFO', {'beginDate': '2026-09-30', 'endDate': '2026-09-30'},
              size=100))
    show('HZ aggregate 2021-01-04..08',
         call('RZRQ_HZ_INFO', {'beginDate': '2021-01-04', 'endDate': '2021-01-08'},
              size=100))


if __name__ == '__main__':
    main()
