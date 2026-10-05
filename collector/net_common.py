"""Shared polite-HTTP helpers for official exchange collectors.

- urllib only (no third-party deps)
- per-host minimum interval throttle + jitter
- retry with exponential backoff on network errors / 5xx / empty reads
- correct UTF-8 decoding (unlike PowerShell IWR which mangles it)
"""
from __future__ import annotations
import json
import random
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0 Safari/537.36')

DEFAULT_HEADERS = {
    'User-Agent': UA,
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}


class ThrottledClient:
    """Thread-safe per-host rate limiter: even with N worker threads, the
    wall-clock interval between two requests to the same host never drops
    below min_interval_s (the throttle is a global serialized section)."""

    def __init__(self, min_interval_s: float = 0.25, max_retries: int = 5):
        self.min_interval = min_interval_s
        self.max_retries = max_retries
        self._last_hit: dict[str, float] = {}
        self._lock = threading.Lock()
        self.n_requests = 0
        self.n_retries = 0

    def _throttle(self, host: str):
        with self._lock:
            now = time.time()
            last = self._last_hit.get(host, 0.0)
            wait = self.min_interval - (now - last)
            if wait > 0:
                time.sleep(wait + random.uniform(0, 0.05))
            self._last_hit[host] = time.time()

    def get_json(self, url: str, extra_headers: dict | None = None,
                 timeout_s: float = 25.0):
        headers = dict(DEFAULT_HEADERS)
        if extra_headers:
            headers.update(extra_headers)
        last_exc = None
        for attempt in range(self.max_retries):
            self._throttle(urllib.parse.urlsplit(url).netloc)
            try:
                self.n_requests += 1
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=timeout_s) as r:
                    raw = r.read()
                if not raw:
                    raise IOError('empty response body')
                text = raw.decode('utf-8', errors='strict')
                return json.loads(text)
            except (urllib.error.URLError, urllib.error.HTTPError, IOError,
                    TimeoutError, json.JSONDecodeError) as exc:
                last_exc = exc
                self.n_retries += 1
                backoff = min(30.0, (2 ** attempt)) + random.uniform(0, 1.5)
                time.sleep(backoff)
        raise RuntimeError(f'GET failed after {self.max_retries} retries: '
                           f'{url} :: {last_exc!r}')


def qs(params: dict) -> str:
    return urllib.parse.urlencode(params, safe=',')
