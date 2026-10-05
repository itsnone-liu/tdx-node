"""Test SSE margin commonSoaQuery raw URL variants."""
import json
import urllib.request

H = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0',
     'Referer': 'http://www.sse.com.cn/market/othersdata/margin/detail/'}
BASE = ('http://query.sse.com.cn/commonSoaQuery.do?'
        'isPagination=true&pageHelp.pageSize=25&pageHelp.pageNo=1'
        '&pageHelp.beginPage=1&pageHelp.cacheSize=1&pageHelp.endPage=1')
TESTS = [
    ('HZ wide', f'{BASE}&sqlId=RZRQ_HZ_INFO&beginDate=2026-09-01&endDate=2026-09-30'),
    ('MX date', f'{BASE}&sqlId=RZRQ_MX_INFO&beginDate=2026-09-30&endDate=2026-09-30'),
    ('MX stock', f'{BASE}&sqlId=RZRQ_MX_INFO&stockCode=600000&beginDate=2026-09-28&endDate=2026-09-30'),
]


def main():
    for tag, url in TESTS:
        try:
            req = urllib.request.Request(url, headers=H)
            with urllib.request.urlopen(req, timeout=25) as r:
                obj = json.loads(r.read().decode('utf-8'))
        except Exception as exc:
            print(f'=== {tag} EXC {exc!r}')
            continue
        ph = obj.get('pageHelp') or {}
        rows = ph.get('data') or []
        print(f'=== {tag}: rows={len(rows)} total={ph.get("total")}')
        if rows:
            print('  fields:', list(rows[0].keys()))
            print('  ', json.dumps(rows[0], ensure_ascii=False)[:280])


if __name__ == '__main__':
    main()
