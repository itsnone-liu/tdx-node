"""Probe unlock (lockshare) file history depth via regex date extraction."""
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, r'D:\tdx-node\tdx-tq-v773\PYPlugins\user')
from tqcenter import tq

DATA = Path(r'D:\tdx-node\tdx-tq-v773\PYPlugins\data')


def main():
    tq.initialize(r'D:\tdx-node\tdx-tq-v773\PYPlugins\user\daily_archive_anchor.py')
    for code, num in [('000078.SZ', '000078'), ('688318.SH', '688318'),
                      ('600519.SH', '600519')]:
        msg = tq.download_file(code, '20260930', 7)
        time.sleep(0.8)
        p = DATA / f'lockshare{num}.json'
        if p.exists():
            raw = p.read_text(encoding='utf-8', errors='replace')
            dates = sorted(set(re.findall(r'20[12]\d[01]\d[0-3]\d', raw)))
            print(f'{code} ok={"ErrorId" in (msg or "") and "0" in (msg or "")} '
                  f'bytes={p.stat().st_size} n_dates={len(dates)} '
                  f'range={dates[0] if dates else "-"}->{dates[-1] if dates else "-"}')
            print('  dates:', dates)
        else:
            print(f'{code} file missing')
    tq.close()


if __name__ == '__main__':
    main()
