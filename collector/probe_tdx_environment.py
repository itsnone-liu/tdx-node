#!/usr/bin/env python3
"""Read-only TDX environment probe. Emits a JSON capability baseline."""
from __future__ import annotations

import argparse
import hashlib
import json
import socket
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def count_day(root: Path, market: str) -> dict:
    folder = root / "vipdoc" / market / "lday"
    files = list(folder.glob("*.day")) if folder.exists() else []
    newest = max((p.stat().st_mtime for p in files), default=None)
    return {
        "path": str(folder),
        "count": len(files),
        "bytes": sum(p.stat().st_size for p in files),
        "newest_mtime": datetime.fromtimestamp(newest, timezone.utc).isoformat() if newest else None,
    }


def port_open(host: str, port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.4)
        return s.connect_ex((host, port)) == 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=r"D:\new_tdx")
    ap.add_argument("--output")
    args = ap.parse_args()
    root = Path(args.root)
    exe = root / "TdxW.exe"
    tqcenter = [str(p) for p in root.rglob("tqcenter.py")] if root.exists() else []
    result = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "exists": root.exists(),
        "tdxw": {
            "exists": exe.exists(),
            "bytes": exe.stat().st_size if exe.exists() else None,
            "sha256": sha256(exe) if exe.exists() else None,
        },
        "pyplugins_exists": (root / "PYPlugins").exists(),
        "tqcenter": tqcenter,
        "localhost_17709_open": port_open("127.0.0.1", 17709),
        "markets": {m: count_day(root, m) for m in ("sh", "sz", "bj")},
    }
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
