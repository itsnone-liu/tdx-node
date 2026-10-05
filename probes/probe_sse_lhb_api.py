"""Probe SSE daily trade public info (LHB) endpoints.

1. main board:  query.sse.com.cn/marketdata/tradedata/queryAllTradeOpenDate.do
               params: token=QUERY, tradeDate=YYYYMMDD, flag=1
2. STAR board: queryKCBTradeInfo.do (tradeDate, flag/refType/secCode)
               queryKCBDeptInfo.do (orderB/orderS, tradeDate, refType, secCode)

SSE requires Referer www.sse.com.cn (else 403).
"""
import json
import urllib.request

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0 Safari/537.36')
Q = 'http://query.sse.com.cn/marketdata/tradedata/'


def get(path, params):
    qs = '&'.join(f'{k}={v}' for k, v in params.items())
    url = Q + path + '?' + qs
    req = urllib.request.Request(url, headers={
        'User-Agent': UA, 'Referer': 'http://www.sse.com.cn/'})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode('utf-8'))


def brief(tag, obj, depth=0):
    def shape(o, d=0):
        if isinstance(o, dict):
            return {k: shape(v, d + 1) for k, v in list(o.items())[:12]} if d < 2 else '...'
        if isinstance(o, list):
            return [shape(o[0], d + 1), f'...len={len(o)}'] if o else []
        return o
    print(f'=== {tag}')
    print(json.dumps(shape(obj), ensure_ascii=False, default=str)[:1800])


def main():
    # 1) main board daily list, 2026-09-30
    try:
        obj = get('queryAllTradeOpenDate.do',
                  {'token': 'QUERY', 'tradeDate': '20260930', 'flag': '1'})
        brief('queryAllTradeOpenDate 20260930 flag=1', obj)
    except Exception as exc:
        print(f'=== main EXC {exc!r}')

    # 2) STAR list same day (no secCode -> full list?)
    try:
        obj = get('queryKCBTradeInfo.do',
                  {'tradeDate': '20260930', 'flag': '2'})
        brief('queryKCBTradeInfo 20260930 flag=2', obj)
    except Exception as exc:
        print(f'=== kcb list EXC {exc!r}')


if __name__ == '__main__':
    main()
