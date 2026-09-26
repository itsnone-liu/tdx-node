#!/usr/bin/env python3
"""Capture raw TPythClient professional-data responses for capability diagnosis."""
from __future__ import annotations
import argparse, ctypes, json, sys, traceback
from datetime import datetime, timezone
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import tqcenter as tc
from tqcenter import tq

ap=argparse.ArgumentParser()
ap.add_argument('--codes',nargs='+',required=True)
ap.add_argument('--fields',nargs='+',required=True)
ap.add_argument('--start',required=True)
ap.add_argument('--end',required=True)
ap.add_argument('--output',required=True)
a=ap.parse_args()
out={'captured_at':datetime.now(timezone.utc).isoformat(),'request':vars(a)}
try:
    tq.initialize(__file__)
    req={'id':tq._get_run_id(),'type':3,'stock_list':a.codes,'table_list':a.fields,
         'start_time':a.start+'000000' if len(a.start)==8 else a.start,
         'end_time':a.end+'000000' if len(a.end)==8 else a.end,
         'stock_page_index':0}
    payload=json.dumps(req,ensure_ascii=False).encode('utf-8')
    ptr=tc.dll.GetProDataInStr(tq._get_run_id(),payload,600000)
    raw=ptr.decode('utf-8') if ptr else None
    out.update(status='success',run_id=tq._get_run_id(),wire_request=req,raw_response=raw)
    try: out['parsed_response']=json.loads(raw) if raw else None
    except Exception as exc: out['parse_error']=repr(exc)
except BaseException as exc:
    out.update(status='error',error_type=type(exc).__name__,error=str(exc),traceback=traceback.format_exc())
finally:
    try:tq.close()
    except Exception:pass
Path(a.output).write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8')
print(json.dumps(out,ensure_ascii=False,indent=2,default=str))
