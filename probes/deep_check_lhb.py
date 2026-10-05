"""Deep checks on accumulated LHB raw:
  1. zero-row days in state — true trading days with no data = problem
  2. cross-foot: SZSE list rows carry per-stock amounts; compare with the
     sum of seat amounts from saved detail files (top5 disclosed == list amt)
  3. SSE: every list row carries both-side seats inline — verify B/S counts
"""
import json
from pathlib import Path

NODE = Path(r'D:\tdx-node')
RAW = NODE / 'lhb' / 'raw'
STATE = json.loads((NODE / 'lhb' / 'backfill_state.json')
                   .read_text(encoding='utf-8'))


def zero_rows():
    for day, rec in sorted(STATE.items()):
        if not (rec.get('szse_list_rows') or rec.get('sse_main_rows')
                or rec.get('sse_star_rows')):
            print('zero-row day:', day, {k: v for k, v in rec.items()
                                         if k != 'retrieved_at'})


def szse_crossfoot(day: str):
    """Compare list-row amounts vs detail seat sums for one day."""
    list_rows = []
    for fp in sorted((RAW / 'szse_list').glob(f'{day}_p*.json')):
        for cat in json.loads(fp.read_text(encoding='utf-8')):
            if cat.get('metadata', {}).get('tabkey') == 'tab1':
                list_rows.extend(cat.get('data') or [])
    if not list_rows:
        print(f'{day}: no list rows')
        return
    print(f'{day}: {len(list_rows)} list rows; sample fields:',
          list(list_rows[0].keys()))
    r0 = list_rows[0]
    print('  sample row:', json.dumps(r0, ensure_ascii=False)[:400])
    code = (r0.get('zqdm') or '').strip()
    fp = RAW / 'szse_detail' / f'{day}_{code}_0901.json'
    if not fp.exists():
        fp = next((RAW / 'szse_detail').glob(f'{day}_{code}_*.json'), None)
    if fp:
        obj = json.loads(fp.read_text(encoding='utf-8'))
        for cat in obj:
            if cat.get('metadata', {}).get('tabkey') == 'tab2':
                d = cat.get('data') or []
                print(f'  detail {fp.name}: {len(d)} seat rows; sample:',
                      json.dumps(d[0], ensure_ascii=False)[:300] if d else '-')


def sse_inline_check(day: str):
    fp = RAW / 'sse_main' / f'{day}.json'
    obj = json.loads(fp.read_text(encoding='utf-8'))
    rows = (obj.get('pageHelp') or {}).get('data') or []
    nb = sum(1 for r in rows if (r.get('branchNameB') or '').strip())
    ns = sum(1 for r in rows if (r.get('branchNameS') or '').strip())
    print(f'{day} sse_main: {len(rows)} rows; rows with buy seats {nb}, '
          f'with sell seats {ns}')
    if rows:
        r = rows[0]
        print('  sample:', json.dumps(
            {k: v for k, v in r.items()
             if 'branch' in k or k in ('SECURITY_CODE', 'SECURITY_NAME_ABBR')},
            ensure_ascii=False)[:500])


if __name__ == '__main__':
    print('--- zero-row days ---')
    zero_rows()
    print('--- szse crossfoot 20210222 ---')
    szse_crossfoot('20210222')
    print('--- sse inline 20210222 ---')
    sse_inline_check('20210222')
