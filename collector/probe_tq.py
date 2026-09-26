#!/usr/bin/env python3
"""Minimal TdxQuant probe; run from a TQ client's PYPlugins/user folder.

It preserves raw responses for audit. No trading functions are called.
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="20240101")
    ap.add_argument("--end", default="20260918")
    ap.add_argument("--codes", nargs="+", default=["510300.SH", "510050.SH", "159919.SZ"])
    ap.add_argument("--tq-path", default=r"D:\tdx-node\tdx-tq-v773\PYPlugins\user")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    sys.path.insert(0, args.tq_path)
    out = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "script": str(Path(__file__).resolve()),
        "python": sys.version,
        "request": {"codes": args.codes, "fields": ["GP51", "GP52"], "start": args.start, "end": args.end},
    }
    try:
        from tqcenter import tq
        out["import_tqcenter"] = "ok"
        init_result = tq.initialize(__file__)
        out["initialize"] = repr(init_result)
        out["response"] = tq.get_gpjy_value(
            stock_list=args.codes,
            field_list=["GP51", "GP52"],
            start_time=args.start,
            end_time=args.end,
        )
        out["status"] = "success"
        rc = 0
    except Exception as exc:
        out["status"] = "error"
        out["error_type"] = type(exc).__name__
        out["error"] = str(exc)
        out["traceback"] = traceback.format_exc()
        rc = 1
    Path(args.output).write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
