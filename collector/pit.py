# -*- coding: utf-8 -*-
"""PIT (Point-In-Time) 口径落地 —— CD-0 冻结规则 (2026-10-12 用户指令落地)。

每条慢频数据记录 available_at = 该数据真正可被公众获取的时刻（北京时间,
ISO8601 带时区）。回测取数用 `available_at <= 决策时刻` 过滤, 不用 trade_date,
以杜绝未来函数 (look-ahead bias)。

公布时刻规则 (均为 T 日收盘 15:00 之后 → CD-0 不变量
「当日盘中决策只能用昨日及更早的数据」在任何规则下都成立):

  dataset  exchange  时刻        依据
  margin   SSE       T 16:30     观测: 收盘后即可拉到, 16:30 保守取值
  margin   SZSE      T 17:30     观测: 2026-10-09 / 10-12 均为 17:30 挂出
  block    SSE       T 17:00     交易所盘后数据公告时段, 保守取值
  block    SZSE      T 17:00     同上
  lhb      SSE       T 18:00     榜单盘后定稿时段, 保守取值
  lhb      SZSE      T 18:00     同上

holders (月度) 与机构 top10 (季度) 尚无 CSV 管道; 待其建管道时在各自的
manifest 里记 fetched_at 并按披露日规则推导 available_at, 本模块规则表
届时扩展。

用法 (normalizer main 写盘前):
    import pit
    pit.stamp(ROWS, 'margin')           # 原地补 available_at 列
    COLS += ['available_at']
"""
from __future__ import annotations

PUBLISH = {  # (dataset, exchange) -> 'HH:MM' on trade_date
    ('margin', 'SSE'): '16:30',
    ('margin', 'SZSE'): '17:30',
    ('block', 'SSE'): '17:00',
    ('block', 'SZSE'): '17:00',
    ('lhb', 'SSE'): '18:00',
    ('lhb', 'SZSE'): '18:00',
}


def available_at(dataset: str, exchange: str, trade_date: str) -> str:
    hm = PUBLISH.get((dataset, exchange)) or '23:59'  # 未知源按当日最晚, 绝不提前
    return f'{trade_date}T{hm}:00+08:00'


def stamp(rows: list[dict], dataset: str) -> int:
    """原地给每行补 available_at; 返回行数。幂等: 已有正确值则跳过重写。"""
    for r in rows:
        r['available_at'] = available_at(dataset, r.get('exchange', ''),
                                         r['trade_date'])
    return len(rows)
