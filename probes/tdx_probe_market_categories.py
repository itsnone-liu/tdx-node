#!/usr/bin/env python3
"""Enumerate TdxQuant stock category codes introduced after documented market 53."""
import json,sys
from datetime import datetime,timezone
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from tqcenter import tq
out={'captured_at':datetime.now(timezone.utc).isoformat(),'categories':{}}
try:
 tq.initialize(__file__)
 for market in range(54,91):
  try:
   v=tq.get_stock_list(str(market),list_type=1)
   out['categories'][str(market)]={'count':len(v),'sample':v[:10]}
  except Exception as e:out['categories'][str(market)]={'error':repr(e)}
finally:
 try:tq.close()
 except:pass
Path(r'D:\tdx-node\raw\tq_market_categories_54_90.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in out['categories'].items() if v.get('count',0)>0 or v.get('error')},ensure_ascii=False,indent=2))
