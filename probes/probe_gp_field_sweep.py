"""Brute-force probe GP1..GP60 on 600519.SH over a short window.

Known so far: GP51/GP52 (ETF规模) = paid-null; GP03/GP11-13 (两融历史) = paid.
This sweep finds which GP fields the FREE account returns and what the values
look like (values are printed so semantics can be inferred).
"""
import sys
import json

sys.path.insert(0, r'D:\tdx-node\tdx-tq-v773\PYPlugins\user')
from tqcenter import tq


def main():
    tq.initialize(r'D:\tdx-node\tdx-tq-v773\PYPlugins\user\daily_archive_anchor.py')
    res = {}
    for n in range(1, 61):
        field = f'GP{n}'
        try:
            out = tq.get_gpjy_value(stock_list=['600519.SH'],
                                    field_list=[field],
                                    start_time='20240102',
                                    end_time='20240110')
            s = json.dumps(out, ensure_ascii=False, default=str)
            res[field] = s
        except Exception as exc:
            res[field] = f'EXC {exc!r}'
    tq.close()

    for k, v in res.items():
        tag = 'NULL' if ('null' in v and 'Value' in v) else ('EXC' if v.startswith('EXC') else 'DATA')
        # print compact: DATA fields in full, NULL/EXC one line
        v_short = v if len(v) < 300 else v[:300] + '...'
        print(f'{k} [{tag}] {v_short}')


if __name__ == '__main__':
    main()
