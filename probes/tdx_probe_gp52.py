#!/usr/bin/env python3
"""Read-only TdxQuant probe for GP51/GP52; no trading calls."""
from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

# The machine's default python is an embedded distribution whose ._pth file
# omits the script directory, so add the official PYPlugins/user folder explicitly.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from tqcenter import tq


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="20260901")
    ap.add_argument("--end", default="20260924")
    ap.add_argument("--codes", nargs="+", default=["510300.SH", "510050.SH", "159919.SZ"])
    ap.add_argument("--fields", nargs="+", default=["GP51", "GP52"])
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    out = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "script": str(Path(__file__).resolve()),
        "python": sys.version,
        "request": {"codes": args.codes, "fields": args.fields, "start": args.start, "end": args.end},
    }
    try:
        tq.initialize(__file__)
        out["initialize"] = "ok"
        out["response"] = tq.get_gpjy_value(
            stock_list=args.codes,
            field_list=args.fields,
            start_time=args.start,
            end_time=args.end,
        )
        out["status"] = "success"
        rc = 0
    except BaseException as exc:
        out["status"] = "error"
        out["error_type"] = type(exc).__name__
        out["error"] = str(exc)
        out["traceback"] = traceback.format_exc()
        rc = 1
    finally:
        try:
            tq.close()
        except Exception:
            pass
    Path(args.output).write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
