"""Systematic variant sweep for SSE RZRQ_MX_INFO (margin per-stock)."""
import json
import urllib.parse
import urllib.request

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0'
PAG = {'isPagination': 'true', 'pageHelp.pageSize': '25', 'pageHelp.pageNo': '1',
       'pageHelp.beginPage': '1', 'pageHelp.cacheSize': '1', 'pageHelp.endPage': '1'}


def get(url):
    req = urllib.request.Request(url, headers={
        'User-Agent': UA,
        'Referer': 'http://www.sse.com.cn/market/othersdata/margin/detail/'})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode('utf-8'))


def variants():
    base = dict(PAG)
    base['sqlId'] = 'RZRQ_MX_INFO'
    yield 'preStock+range', {**base, 'preStockCode': '600000',
                             'beginDate': '2026-09-28', 'endDate': '2026-09-30'}
    yield 'compact dates', {**base, 'stockCode': '',
                            'beginDate': '20260930', 'endDate': '20260930'}
    yield 'jsonCallBack', {**base, 'jsonCallBack': 'jQuery1',
                           'beginDate': '2026-09-30', 'endDate': '2026-09-30'}
    yield 'no pagination keys', {'sqlId': 'RZRQ_MX_INFO', 'isPagination': 'false',
                                 'beginDate': '2026-09-30', 'endDate': '2026-09-30'}


def main():
    for tag, params in variants():
        url = ('http://query.sse.com.cn/commonSoaQuery.do?' +
               urllib.parse.urlencode(params))
        try:
            obj = get(url)
        except Exception as exc:
            print(f'=== {tag} EXC {exc!r}')
            continue
        ph = obj.get('pageHelp') or {}
        rows = ph.get('data') or []
        print(f'=== {tag}: rows={len(rows)} total={ph.get("total")} '
              f'keys={list(obj.keys())[:8]}')
        if rows:
            print('  fields:', list(rows[0].keys()))
            print('  ', json.dumps(rows[0], ensure_ascii=False)[:280])


if __name__ == '__main__':
    main()
