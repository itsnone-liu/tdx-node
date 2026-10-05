"""SSE margin: POST form-encoded to commonSoaQuery.do (mirrors page getJSONP),
plus commonQuery.do GET fallback with legacy sqlIds."""
import json
import urllib.parse
import urllib.request

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0'
PAG = {'isPagination': 'true', 'pageHelp.pageSize': '25', 'pageHelp.pageNo': '1',
       'pageHelp.beginPage': '1', 'pageHelp.cacheSize': '1', 'pageHelp.endPage': '1'}


def post_soa(sqlid, extra):
    body = dict(PAG)
    body['sqlId'] = sqlid
    body.update(extra)
    data = urllib.parse.urlencode(body).encode()
    req = urllib.request.Request(
        'http://query.sse.com.cn/commonSoaQuery.do', data=data,
        headers={'User-Agent': UA,
                 'Referer': 'http://www.sse.com.cn/market/othersdata/margin/detail/',
                 'Content-Type': 'application/x-www-form-urlencoded'})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode('utf-8'))


def get_common(sqlid, extra):
    params = dict(PAG)
    params['sqlId'] = sqlid
    params.update(extra)
    url = ('http://query.sse.com.cn/commonQuery.do?' +
           urllib.parse.urlencode(params))
    req = urllib.request.Request(url, headers={
        'User-Agent': UA, 'Referer': 'http://www.sse.com.cn/'})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode('utf-8'))


def show(tag, obj):
    ph = obj.get('pageHelp') or obj
    rows = ph.get('data') or []
    print(f'=== {tag}: rows={len(rows)} total={ph.get("total")}')
    if rows:
        print('  fields:', list(rows[0].keys()))
        print('  ', json.dumps(rows[0], ensure_ascii=False)[:280])
    return rows


def main():
    show('POST MX 2026-09-30',
         post_soa('RZRQ_MX_INFO',
                  {'beginDate': '2026-09-30', 'endDate': '2026-09-30'}))
    show('GET legacy MX',
         get_common('COMMON_SSE_ZQPZ_RZRQXX_MX_L',
                    {'beginDate': '2026-09-30', 'endDate': '2026-09-30'}))
    show('GET legacy MX2',
         get_common('COMMON_SSE_XXPL_RZRQXX_MX_L',
                    {'beginDate': '2026-09-30', 'endDate': '2026-09-30'}))


if __name__ == '__main__':
    main()
