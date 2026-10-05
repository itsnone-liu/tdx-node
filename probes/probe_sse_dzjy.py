"""Live-test SSE block trade (dzjyxx) L_1 sqlId: date filter + big page."""
import json
import urllib.parse
import urllib.request

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0'
URL = 'http://query.sse.com.cn/commonQuery.do'


def call(sqlid, extra, size=1000, page=1):
    params = {'isPagination': 'true', 'pageHelp.pageSize': str(size),
              'pageHelp.pageNo': str(page), 'pageHelp.beginPage': str(page),
              'pageHelp.cacheSize': '1', 'pageHelp.endPage': str(page),
              'sqlId': sqlid}
    params.update(extra)
    url = URL + '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        'User-Agent': UA,
        'Referer': 'http://www.sse.com.cn/disclosure/diclosure/block/deal/dzjyxx/'})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode('utf-8'))


def show(tag, obj):
    ph = obj.get('pageHelp') or {}
    rows = ph.get('data') or ph.get('result') or []
    print(f'=== {tag}: rows={len(rows)} total={ph.get("total")}')
    if rows:
        print('  fields:', list(rows[0].keys()))
        for r in rows[:2]:
            print('  ', json.dumps(r, ensure_ascii=False)[:300])


def main():
    show('L1 dashed', call('COMMON_SSE_XXPL_JYXXPL_DZJYXX_L_1',
                           {'stockId': '', 'startDate': '2026-09-30',
                            'endDate': '2026-09-30'}))
    show('L1 compact', call('COMMON_SSE_XXPL_JYXXPL_DZJYXX_L_1',
                            {'stockId': '', 'startDate': '20260930',
                             'endDate': '20260930'}))
    show('L1 2021 compact', call('COMMON_SSE_XXPL_JYXXPL_DZJYXX_L_1',
                                 {'stockId': '', 'startDate': '20210105',
                                  'endDate': '20210105'}))


if __name__ == '__main__':
    main()
