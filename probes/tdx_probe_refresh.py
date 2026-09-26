#!/usr/bin/env python3
"""Read-only TQ cache refresh probe; does not call trading functions."""
from __future__ import annotations
import json, sys, traceback
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from tqcenter import tq

out = {"captured_at": datetime.now(timezone.utc).isoformat(), "script": str(Path(__file__).resolve())}
try:
    tq.initialize(__file__)
    out["initialize"] = "ok"
    out["refresh_cache"] = tq.refresh_cache(market="AG", force=True)
    out["status"] = "success"
except BaseException as exc:
    out.update(status="error", error_type=type(exc).__name__, error=str(exc), traceback=traceback.format_exc())
finally:
    try: tq.close()
    except Exception: pass
Path(r"D:\tdx-node\raw\tq_refresh_cache_force.json").write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2,default=str))
