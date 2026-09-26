#!/usr/bin/env python3
"""Probe non-trading TdxQuant capabilities available to the logged-in account."""
from __future__ import annotations
import json, sys, traceback
from datetime import datetime, timezone
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from tqcenter import tq

OUT=Path(r"D:\tdx-node\raw\tq_free_capabilities.json")
out={"captured_at":datetime.now(timezone.utc).isoformat(),"script":str(Path(__file__).resolve()),"tests":{}}

def simplify(v):
    if hasattr(v,"to_dict"):
        try:return v.reset_index().to_dict(orient="records")
        except Exception:return str(v)
    return v

def test(name, fn):
    try:
        v=fn();out["tests"][name]={"status":"success","value":simplify(v)}
    except BaseException as exc:
        out["tests"][name]={"status":"error","error_type":type(exc).__name__,"error":str(exc),"traceback":traceback.format_exc()}

try:
    tq.initialize(__file__);out["initialize"]="ok"
    test("divid_600519_2021_2026",lambda:tq.get_divid_factors("600519.SH","20210101","20260924"))
    test("gb_600519_2021_2026",lambda:tq.get_gb_info_by_date("600519.SH","20210101","20260924"))
    test("etf_list_market31",lambda:tq.get_stock_list("31",list_type=0))
    test("etf_track_000300",lambda:tq.get_trackzs_etf_info("000300.SH"))
    # Enumerate documented/likely list modes without assuming their semantics.
    for lt in (0,1,2,3,4,5):
        test(f"stock_list_market5_list_type{lt}",lambda lt=lt:tq.get_stock_list("5",list_type=lt))
    test("download_etf_pcf_510300_20260924",lambda:tq.download_file("510300.SH","20260924",2))
    test("download_etf_pcf_159919_20260924",lambda:tq.download_file("159919.SZ","20260924",2))
    test("download_recent_lhb",lambda:tq.download_file("688318.SH","20260924",6))
    test("download_recent_unlock",lambda:tq.download_file("688318.SH","20260924",7))
    test("download_top10_600519_20250101",lambda:tq.download_file("600519.SH","20250101",1))
    out["status"]="success"
except BaseException as exc:
    out.update(status="error",error_type=type(exc).__name__,error=str(exc),traceback=traceback.format_exc())
finally:
    try:tq.close()
    except Exception:pass
OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str)+"\n",encoding="utf-8")
print(json.dumps({"status":out.get("status"),"initialize":out.get("initialize"),"tests":{k:{"status":v.get("status"),"value_type":type(v.get("value")).__name__,"value_len":len(v.get("value")) if isinstance(v.get("value"),(list,dict,str)) else None,"error":v.get("error")} for k,v in out["tests"].items()}},ensure_ascii=False,indent=2))
