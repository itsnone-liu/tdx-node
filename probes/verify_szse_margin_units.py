"""Verify SZSE margin column units: rqyl(万股) x close(元) ~= jrrjye(万元?).
Uses one SZSE API call + TDX local price data."""
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, r'D:\tdx-node\tdx-tq-v773\PYPlugins\user')


def szse_tab2(day_iso):
    H = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0',
         'Referer': 'https://www.szse.cn/'}
    params = {'SHOWTYPE': 'JSON', 'CATALOGID': '1837_xxpl', 'TABKEY': 'tab2',
              'txtDate': day_iso, 'PAGENO': '1', 'random': '0.5'}
    url = ('https://www.szse.cn/api/report/ShowReport/data?' +
           urllib.parse.urlencode(params))
    req = urllib.request.Request(url, headers=H)
    with urllib.request.urlopen(req, timeout=25) as r:
        obj = json.loads(r.read().decode('utf-8'))
    for cat in obj:
        if cat.get('metadata', {}).get('tabkey') == 'tab2':
            return cat.get('data') or []
    return []


def tdx_close(code, day):
    from tqcenter import tq
    tq.initialize(r'D:\tdx-node\tdx-tq-v773\PYPlugins\user\daily_archive_anchor.py')
    try:
        bars = tq.get_price(code=code, market='SZ', start_time=day,
                            end_time=day, cycle='day')
        if hasattr(bars, 'to_dict'):
            bars = bars.to_dict('records')
        if isinstance(bars, dict):
            bars = [bars]
        for b in (bars or []):
            d = str(b.get('datetime') or b.get('date') or '')
            if d.replace('-', '').startswith(day):
                for k in ('close', '收盘价', 'c'):
                    if b.get(k) is not None:
                        return float(b[k])
    finally:
        tq.close()
    return None


def main():
    day_iso, day = '2021-01-05', '20210105'
    rows = szse_tab2(day_iso)
    print(f'{len(rows)} tab2 rows')
    checked = 0
    for r in rows[:8]:
        code = (r.get('zqdm') or '').strip()
        rqyl = float(str(r.get('jrrjyl')).replace(',', '') or 0)  # 万股?
        jrrjye = float(str(r.get('jrrjye')).replace(',', '') or 0)  # 万元?
        if rqyl <= 0 or code.startswith(('39', '15', '16', '18')):
            continue
        close = tdx_close(code, day)
        if not close:
            print(f'{code}: no TDX close')
            continue
        rqye_implied = rqyl * 1e4 * close / 1e4  # 万元
        ratio = rqye_implied / jrrjye if jrrjye else float('nan')
        print(f'{code} rqyl={rqyl}万 close={close} -> rqye={rqye_implied:.1f}万 '
              f'| jrrjye={jrrjye} | ratio={ratio:.3f}')
        checked += 1
        if checked >= 5:
            break


if __name__ == '__main__':
    main()
