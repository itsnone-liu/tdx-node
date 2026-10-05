"""Extract CATALOGIDs + query params from SZSE block-trade and margin pages."""
import re
import sys
import urllib.request
from pathlib import Path

H = {'Referer': 'https://www.szse.cn/disclosure/',
     'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                   'AppleWebKit/537.36 Chrome/124.0 Safari/537.36'}
PAGES = {
    'block_equity': 'https://www.szse.cn/disclosure/deal/block/equity/index.html',
    'margin_margin': 'https://www.szse.cn/disclosure/margin/margin/index.html',
}


def fetch(url):
    req = urllib.request.Request(url, headers=H)
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode('utf-8', errors='replace')


def main():
    for tag, url in PAGES.items():
        try:
            html = fetch(url)
        except Exception as exc:
            print(f'=== {tag} FETCH FAIL {exc!r}')
            continue
        out = Path(r'D:\tdx-node\raw') / f'szse_{tag}.html'
        out.write_text(html, encoding='utf-8')
        cats = sorted(set(re.findall(r'CATALOGID["\']?\s*[:=]\s*["\']([^"\']+)["\']', html)))
        cats2 = sorted(set(re.findall(r'catalogid=([a-z0-9_]+)', html, re.I)))
        print(f'=== {tag}: len={len(html)} CATALOGID-literal={cats} url-param={cats2}')
        for js in sorted(set(re.findall(r'src="(/js/[^"]+\.js[^"]*)"', html))):
            print('   js:', js)


if __name__ == '__main__':
    main()
