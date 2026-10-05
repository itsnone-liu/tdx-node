"""Phase 0 for ② block trades (大宗交易) and ③ margin (融资融券):
discover SZSE official endpoints from its disclosure nav pages.
Minimal request count (bg LHB backfill is running against SZSE)."""
import re
import sys
from pathlib import Path

sys.path.insert(0, r'D:\tdx-node')
from collector.net_common import ThrottledClient  # noqa: E402
import urllib.request  # noqa: E402
import urllib.parse  # noqa: E402

cli = ThrottledClient(min_interval_s=0.6, max_retries=3)
H = {'Referer': 'https://www.szse.cn/disclosure/',
     'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                   'AppleWebKit/537.36 Chrome/124.0 Safari/537.36'}

PAGES = [
    ('nav', 'https://www.szse.cn/disclosure/'),
]


def fetch_html(url):
    req = urllib.request.Request(url, headers=H)
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode('utf-8', errors='replace')


def main():
    html = fetch_html(PAGES[0][1])
    out = Path(r'D:\tdx-node\raw\szse_disclosure_nav.html')
    out.parent.mkdir(exist_ok=True)
    out.write_text(html, encoding='utf-8')
    links = sorted(set(re.findall(
        r'href="(/disclosure/[^"#?]+)"[^>]*>([^<]{2,20})<', html)))
    for href, text in links:
        print(href, '  ', text.strip())


if __name__ == '__main__':
    main()
