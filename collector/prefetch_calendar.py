"""Prefill trading calendar 2021-01-01..2021-08-01 (TDX local calendar starts
2021-08-02). Derives trading days from the SSE Composite (000001.SH) daily
klines via eastmoney's public kline endpoint (index published by the
exchange; EM here is only a transport). Output: manifests/calendar_prefill_2021.json
"""
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from net_common import DEFAULT_HEADERS  # noqa: E402

OUT = Path(r'D:\tdx-node\manifests\calendar_prefill_2021.json')
URL = ('https://push2his.eastmoney.com/api/qt/stock/kline/get?'
       'secid=1.000001&fields1=f1,f2,f3,f4,f5,f6&'
       'fields2=f51,f52&klt=101&fqt=0&beg=20210101&end=20210801')


def main():
    req = urllib.request.Request(URL, headers=dict(DEFAULT_HEADERS))
    with urllib.request.urlopen(req, timeout=30) as r:
        obj = json.loads(r.read().decode('utf-8'))
    klines = obj.get('data', {}).get('klines') or []
    days = [k.split(',')[0].replace('-', '') for k in klines]
    OUT.write_text(json.dumps(days, ensure_ascii=False), encoding='utf-8')
    print(f'{len(days)} trading days: {days[0]} .. {days[-1]}')


if __name__ == '__main__':
    main()
