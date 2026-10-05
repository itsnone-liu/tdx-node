"""Verify SSE RZRQ_MX_INFO supports big pageHelp.pageSize (one call per day)."""
import json
import urllib.parse
import urllib.request

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0'


def call(size, day='20260930', sqlid='RZRQ_MX_INFO'):
    params = {'isPagination': 'true', 'pageHelp.pageSize': str(size),
              'pageHelp.pageNo': '1', 'pageHelp.beginPage': '1',
              'pageHelp.cacheSize': '1', 'pageHelp.endPage': '1',
              'sqlId': sqlid, 'beginDate': day, 'endDate': day}
    url = ('http://query.sse.com.cn/commonSoaQuery.do?' +
           urllib.parse.urlencode(params))
    req = urllib.request.Request(url, headers={
        'User-Agent': UA,
        'Referer': 'http://www.sse.com.cn/market/othersdata/margin/detail/'})
    with urllib.request.urlopen(req, timeout=40) as r:
        obj = json.loads(r.read().decode('utf-8'))
    ph = obj.get('pageHelp') or {}
    rows = ph.get('data') or []
    return len(rows), ph.get('total'), rows[:1]


def main():
    for size in (1000, 3000):
        try:
            n, total, first = call(size)
            print(f'size={size}: got={n} total={total}')
            if first:
                print('  ', json.dumps(first[0], ensure_ascii=False)[:200])
        except Exception as exc:
            print(f'size={size} EXC {exc!r}')
    # 2021 history check
    n, total, first = call(3000, day='20210105')
    print(f'2021-01-05: got={n} total={total}')
    if first:
        print('  ', json.dumps(first[0], ensure_ascii=False)[:200])


if __name__ == '__main__':
    main()
