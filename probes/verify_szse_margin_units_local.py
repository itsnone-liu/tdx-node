"""Verify SZSE margin column units from LOCAL raw (no network):
hypothesis: jrrzye/jrrzmr/jrrjmc/jrrzrjye=亿元, jrrjyl=万股, jrrjye=万元.
Check: jrrjyl(万股)*1e4 * close(元)  ~=  jrrjye(万元)*1e4   (融券余额=余量x价)
Run AFTER the chain has fetched margin/szse raw for some day.
"""
import json
import sys
from pathlib import Path

NODE = Path(r'D:\tdx-node')
RAW = NODE / 'blockmargin' / 'raw' / 'margin' / 'szse'


def szse_rows(day: str):
    iso = f'{day[:4]}-{day[4:6]}-{day[6:]}'
    for fp in sorted(RAW.glob(f'{day}_p1.json')):
        for cat in json.loads(fp.read_text(encoding='utf-8')):
            if cat.get('metadata', {}).get('tabkey') == 'tab2':
                return cat.get('data') or []
    return []


def tdx_close(code: str, day: str):
    sys.path.insert(0, r'D:\tdx-node\tdx-tq-v773\PYPlugins\user')
    from tqcenter import tq
    tq.initialize(r'D:\tdx-node\tdx-tq-v773\PYPlugins\user'
                  r'\daily_archive_anchor.py')
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


def to_f(s):
    try:
        return float(str(s).replace(',', ''))
    except (TypeError, ValueError):
        return 0.0


def main():
    days = sorted({fp.stem.split('_')[0] for fp in RAW.glob('*_p1.json')})
    if not days:
        print('no szse margin raw yet — run after chain fetches it')
        return
    day = days[-1]
    rows = szse_rows(day)
    print(f'{day}: {len(rows)} rows')
    ok = bad = 0
    for r in rows[:10]:
        code = (r.get('zqdm') or '').strip()
        rqyl = to_f(r.get('jrrjyl'))     # 万股?
        rqye = to_f(r.get('jrrjye'))     # 万元?
        if rqyl <= 0 or rqye <= 0 or code.startswith(('39', '15', '16', '18')):
            continue
        close = tdx_close(code, day)
        if not close:
            continue
        implied = rqyl * 1e4 * close / 1e4  # 万元
        ratio = implied / rqye if rqye else float('nan')
        hit = 0.97 <= ratio <= 1.03
        ok += hit
        bad += not hit
        print(f'  {code} rqyl={rqyl:.1f}万 close={close:.2f} '
              f'implied={implied:.0f}万 official={rqye:.0f}万 '
              f'ratio={ratio:.3f} {"OK" if hit else "<-- MISMATCH"}')
    print(f'verdict: {ok} ok / {bad} mismatch '
          f'({"hypothesis HOLDS" if bad == 0 and ok >= 3 else "NEEDS REVIEW"})')


if __name__ == '__main__':
    main()
