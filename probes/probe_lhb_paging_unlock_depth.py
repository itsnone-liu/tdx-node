"""Probe: does download_file(dtype=6, LHB) respect historical down_time (paging)?

If yes -> full LHB history by paging back from today. If no -> file is a fixed
"recent 10 events" window and history needs another source.
Also probe dtype=7 (unlock/lockshare) historical depth the same way.
"""
import sys
import json
import time
from pathlib import Path

sys.path.insert(0, r'D:\tdx-node\tdx-tq-v773\PYPlugins\user')
from tqcenter import tq

DATA = Path(r'D:\tdx-node\tdx-tq-v773\PYPlugins\data')


def lhb_dates(code_num: str):
    p = DATA / f'lhb{code_num}.json'
    if not p.exists():
        return None
    dates = []
    for rec in json.loads(p.read_text(encoding='utf-8')):
        dates.extend(json.loads(rec['data_json']).keys())
    return sorted(dates)


def unlock_dates(code_num: str):
    p = DATA / f'lockshare{code_num}.json'
    if not p.exists():
        return None
    recs = json.loads(p.read_text(encoding='utf-8'))
    dates = []
    for rec in recs:
        inner = json.loads(rec['data_json'])
        if isinstance(inner, list):
            for ev in inner:
                d = ev.get('解禁日期') or ev.get('\u89e3\u7981\u65e5\u671f')
                if d:
                    dates.append(d)
        elif isinstance(inner, dict):
            dates.append(str(inner))
    return sorted(dates)


def main():
    tq.initialize(r'D:\tdx-node\tdx-tq-v773\PYPlugins\user\daily_archive_anchor.py')

    print('--- LHB down_time paging probe (000078.SZ) ---')
    for probe_date in ['20260930', '20240601', '20220101', '20210601']:
        msg = tq.download_file('000078.SZ', probe_date, 6)
        time.sleep(0.8)
        ds = lhb_dates('000078')
        ok = '"ErrorId":"0"' in (msg or '')
        print(f'down_time={probe_date} ok={ok} events={len(ds) if ds else 0} '
              f'range={ds[0] if ds else "-"}->{ds[-1] if ds else "-"}')

    print('--- unlock history depth (000078.SZ + 688318.SH) ---')
    for code, num in [('000078.SZ', '000078'), ('688318.SH', '688318')]:
        msg = tq.download_file(code, '20260930', 7)
        time.sleep(0.8)
        ds = unlock_dates(num)
        print(f'{code}: ok={"ErrorId\":\"0" in (msg or "")} events={len(ds) if ds else 0} '
              f'range={ds[0] if ds else "-"}->{ds[-1] if ds else "-"}')
        p = DATA / f'lockshare{num}.json'
        if p.exists():
            raw = p.read_text(encoding='utf-8')
            print('  raw head:', raw[:400])

    tq.close()


if __name__ == '__main__':
    main()
