"""Dump A-share trading calendar 2021-01-01..today from the TDX client
and extract the SSE refType->reason-name mapping from the saved page JS
(mojibake-repaired)."""
import inspect
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, r'D:\tdx-node\tdx-tq-v773\PYPlugins\user')
from tqcenter import tq  # noqa: E402


def dump_calendar():
    tq.initialize(r'D:\tdx-node\tdx-tq-v773\PYPlugins\user\daily_archive_anchor.py')
    for name in ('get_trading_dates', 'get_trading_calendar'):
        fn = getattr(tq, name, None)
        if fn is None:
            continue
        print(f'trying tq.{name}{inspect.signature(fn)}')
        try:
            for kwargs in ({}, {'market': 'AG'}, {'start_time': '20210101', 'end_time': '20261231'}):
                try:
                    out = fn(**kwargs)
                except TypeError:
                    continue
                s = json.dumps(out, ensure_ascii=False, default=str)
                print(f'  kwargs={kwargs} -> {s[:200]}')
                return out
        except Exception as exc:
            print(f'  EXC {exc!r}')
    tq.close()
    return None


def fix_mojibake(s: str) -> str:
    try:
        return s.encode('latin-1').decode('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def extract_reftypes():
    src = Path(r'D:\tdx-node\raw\sse_search_diclosurePublic_2022.js').read_text(
        encoding='utf-8', errors='replace')
    mapping = {}
    for m in re.finditer(r'disclosureJson\["(\d+)"\]\s*=\s*\{.*?name:\s*"([^"]+)"', src,
                         re.S):
        code, name = m.group(1), fix_mojibake(m.group(2))
        if code not in mapping or len(name) < len(mapping[code]):
            mapping[code] = name
    return mapping


def main():
    cal = dump_calendar()
    if cal is not None:
        Path(r'D:\tdx-node\manifests\trading_calendar_probe.json').write_text(
            json.dumps(cal, ensure_ascii=False, default=str), encoding='utf-8')
        print('calendar probe saved')
    mapping = extract_reftypes()
    Path(r'D:\tdx-node\manifests\sse_reftype_map.json').write_text(
        json.dumps(mapping, ensure_ascii=False, indent=1), encoding='utf-8')
    print('refType mapping:')
    for k in sorted(mapping, key=int):
        print(f'  {k}: {mapping[k]}')


if __name__ == '__main__':
    main()
