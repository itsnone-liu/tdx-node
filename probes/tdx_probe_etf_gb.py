#!/usr/bin/env python3
import json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from tqcenter import tq
out={}
try:
 tq.initialize(__file__)
 for code in ('510300.SH','510050.SH','159919.SZ'):
  try:
   v=tq.get_gb_info_by_date(code,'20210101','20260924')
   out[code]={'count':len(v) if hasattr(v,'__len__') else None,'first':v[:3] if isinstance(v,list) else v,'last':v[-3:] if isinstance(v,list) else v}
  except Exception as e:out[code]={'error':repr(e)}
finally:
 try:tq.close()
 except:pass
Path(r'D:\tdx-node\raw\tq_etf_gb_history.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8')
print(json.dumps(out,ensure_ascii=False,indent=2,default=str))
