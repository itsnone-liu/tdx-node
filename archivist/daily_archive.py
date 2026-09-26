#!/usr/bin/env python3
"""Task 3: TDX daily archivist — forward-PIT snapshot archive (free-account sources only).

Every trading evening this captures the things that are "current snapshot only"
in the free TDX node, so they become OUR point-in-time history from now on:
  - ETF current list (market 31), CSI300 constituents (market 23),
    margin categories 56/57 (labels unresolved — archived raw)
  - ETF PCF for the ETF watchlist (download_file type 2)
  - today's share-capital snapshot for the stock watchlist (single date query)
  - LHB (type 6) / unlock (type 7) recent files for the stock watchlist
  - top-10 holders (type 1) for current year, weekly (Mondays) to stay light

Each artifact lands in D:\\tdx-node\\archive\\<YYYYMMDD>\\ with a manifest entry:
retrieved_at, request, file, sha256, bytes. Idempotent per day (--force to redo).

Red lines honored: ETF get_gb_info_by_date is NEVER used (false history);
no credentials are read — the client's own auto-login is the only auth.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import socket
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

NODE_ROOT = Path(r'D:\tdx-node')
CLIENT_DIR = NODE_ROOT / 'tdx-tq-v773'
USER_DIR = CLIENT_DIR / 'PYPlugins' / 'user'
DATA_DIR = CLIENT_DIR / 'PYPlugins' / 'data'
TDX_EXE = CLIENT_DIR / 'TdxW.exe'
ARCHIVE_ROOT = NODE_ROOT / 'archive'
UNIVERSE_FILE = NODE_ROOT / 'manifests' / 'csr84_universe.json'

sys.path.insert(0, str(USER_DIR))
from tqcenter import tq  # noqa: E402

ETF_WATCHLIST = [
    '510300.SH', '510050.SH', '159919.SZ', '159915.SZ',
    '512880.SH', '518880.SH', '513050.SH', '512100.SH',
]
MARKET_SNAPSHOTS = {'31': 'etf_list', '23': 'csi300', '56': 'margin_cat56', '57': 'margin_cat57'}


def sha256_of(fp: Path) -> str:
    h = hashlib.sha256()
    h.update(fp.read_bytes())
    return h.hexdigest()


def port_open(port: int, host='127.0.0.1', timeout=2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def ensure_client(max_wait_s: int = 240) -> int | None:
    """Return TdxW pid if the local HTTP plane is up; start the client if needed."""
    if port_open(17709):
        return pid_of_listener()
    if not TDX_EXE.exists():
        print(f'client exe missing: {TDX_EXE}', file=sys.stderr)
        return None
    subprocess.Popen([str(TDX_EXE)], cwd=str(CLIENT_DIR))
    deadline = time.time() + max_wait_s
    while time.time() < deadline:
        if port_open(17709):
            time.sleep(5)  # settle: login + data ready
            return pid_of_listener()
        time.sleep(5)
    return None


def pid_of_listener() -> int | None:
    try:
        out = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             "(Get-NetTCPConnection -LocalPort 17709 -State Listen | Select-Object -First 1).OwningProcess"],
            capture_output=True, text=True, timeout=15).stdout.strip()
        return int(out) if out.isdigit() else None
    except Exception:
        return None


def tqcenter_version() -> str:
    try:
        txt = (USER_DIR / 'tqcenter.py').read_text(encoding='utf-8', errors='ignore')
        m = re.search(r"Version[:=]\s*[\"']?([\d.]+)", txt)
        if m:
            return m.group(1)
    except Exception:
        pass
    return 'unknown'


def add_entry(manifest: list, name: str, request, fp: Path, day_dir: Path):
    if not fp.exists():
        manifest.append({'name': name, 'request': str(request), 'file': None, 'error': 'file missing'})
        return
    rel = str(fp.relative_to(day_dir))
    manifest.append({
        'name': name,
        'request': str(request),
        'file': rel,
        'bytes': fp.stat().st_size,
        'sha256': sha256_of(fp),
        'retrieved_at': datetime.now(timezone.utc).isoformat(),
    })


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--date', default=datetime.now().strftime('%Y%m%d'))
    args = ap.parse_args()

    day_dir = ARCHIVE_ROOT / args.date
    day_dir.mkdir(parents=True, exist_ok=True)
    manifest_fp = day_dir / 'manifest.json'

    if manifest_fp.exists() and not args.force:
        try:
            man = json.loads(manifest_fp.read_text(encoding='utf-8'))
            if man.get('status') == 'complete':
                print(f'already archived for {args.date} ({len(man.get("artifacts", []))} artifacts); use --force')
                return 0
        except Exception:
            pass

    pid = ensure_client()
    manifest = []
    meta = {
        'node': 'tdx-node free account',
        'archivist_version': '1.0.0',
        'tqcenter_version': tqcenter_version(),
        'client_pid': pid,
        'http_plane': '127.0.0.1:17709',
        'red_lines': [
            'ETF get_gb_info_by_date never used (false history, unique_zgb=1)',
            'GP52/GP03-series gated by paid package — not fetched',
        ],
    }

    try:
        tq.initialize(str(USER_DIR / 'daily_archive_anchor.py'))

        # 1) market category snapshots (list_type=1 returns Code+Name; 2/3 return empty)
        for mkt, label in MARKET_SNAPSHOTS.items():
            try:
                rows = tq.get_stock_list(mkt, list_type=1)
                fp = day_dir / f'{label}.json'
                fp.write_text(json.dumps(rows, ensure_ascii=False, indent=1, default=str), encoding='utf-8')
                add_entry(manifest, label, f'get_stock_list({mkt!r}, list_type=2)', fp, day_dir)
            except Exception as exc:
                manifest.append({'name': label, 'error': repr(exc)})

        # 2) ETF PCF for watchlist
        for code in ETF_WATCHLIST:
            try:
                msg = tq.download_file(code, args.date, 2)
                num = code.split('.')[0]
                src = DATA_DIR / f'etfpcf{num}_{args.date}.json'
                dst = day_dir / f'pcf{num}_{args.date}.json'
                if src.exists():
                    dst.write_bytes(src.read_bytes())
                add_entry(manifest, f'pcf_{code}', f'download_file({code!r},{args.date!r},2)->{msg}',
                          dst if dst.exists() else src, day_dir)
            except Exception as exc:
                manifest.append({'name': f'pcf_{code}', 'error': repr(exc)})
            time.sleep(0.2)

        # 3) today's share-capital snapshot for stock watchlist (valid AS OF TODAY only)
        try:
            codes = json.loads(UNIVERSE_FILE.read_text(encoding='utf-8'))['codes']
        except Exception:
            codes = []
        gb_today = {}
        for code in codes:
            try:
                rows = tq.get_gb_info_by_date(code, args.date, args.date)
                gb_today[code] = rows[-1] if rows else None
            except Exception as exc:
                gb_today[code] = {'error': repr(exc)}
            time.sleep(0.1)
        fp = day_dir / 'gb_today_watchlist.json'
        payload = {
            'as_of': args.date,
            'warning': 'single-date snapshot; historical backfill of this field is current-snapshot backfilled by TDX for ETFs and is NOT point-in-time for anything before archive start',
            'stocks': gb_today,
        }
        fp.write_text(json.dumps(payload, ensure_ascii=False, indent=1, default=str), encoding='utf-8')
        add_entry(manifest, 'gb_today_watchlist', f'get_gb_info_by_date(code,{args.date},{args.date}) x {len(codes)}', fp, day_dir)

        # 4) LHB + unlock recent files for watchlist (small per-stock files)
        file_prefix = {'lhb': 'lhb', 'unlock': 'lockshare'}
        for kind, dtype in (('lhb', 6), ('unlock', 7)):
            got = 0
            for code in codes[:20]:  # keep daily run light; rotate: first 20 by code
                try:
                    tq.download_file(code, args.date, dtype)
                    num = code.split('.')[0]
                    src = DATA_DIR / f'{file_prefix[kind]}{num}.json'
                    if src.exists() and src.stat().st_size > 2:
                        dst = day_dir / f'{kind}_{num}_{args.date}.json'
                        dst.write_bytes(src.read_bytes())
                        add_entry(manifest, f'{kind}_{code}', f'download_file({code!r},{args.date!r},{dtype})', dst, day_dir)
                        got += 1
                    time.sleep(0.15)
                except Exception:
                    pass
            manifest.append({'name': f'{kind}_watchlist', 'files': got, 'note': 'non-empty files only'})

        # 5) holders for current year — weekly (Monday) only
        if datetime.now().weekday() == 0 or args.force:
            year = args.date[:4]
            got = 0
            for code in codes:
                try:
                    tq.download_file(code, f'{year}0101', 1)
                    num = code.split('.')[0]
                    src = DATA_DIR / f'holders{num}_{year}.json'
                    if src.exists() and src.stat().st_size > 10:
                        dst = day_dir / f'holders_{num}_{year}.json'
                        dst.write_bytes(src.read_bytes())
                        add_entry(manifest, f'holders_{code}_{year}', f'download_file({code!r},{year}0101,1)', dst, day_dir)
                        got += 1
                    time.sleep(0.15)
                except Exception:
                    pass
            manifest.append({'name': 'holders_watchlist_yearly', 'files': got})

        status = 'complete'
    except BaseException as exc:
        status = 'error'
        manifest.append({'name': '__fatal__', 'error': f'{type(exc).__name__}: {exc}',
                         'traceback': traceback.format_exc()})
    finally:
        try:
            tq.close()
        except Exception:
            pass

    out = {'date': args.date, 'status': status,
           'completed_at': datetime.now(timezone.utc).isoformat(),
           'meta': meta, 'artifacts': manifest}
    manifest_fp.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding='utf-8')
    print(json.dumps({'date': args.date, 'status': status, 'artifacts': len(manifest)}, ensure_ascii=False))
    return 0 if status == 'complete' else 1


if __name__ == '__main__':
    sys.exit(main())
