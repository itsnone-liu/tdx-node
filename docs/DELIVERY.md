# 免费数据方案 — 交付清单（DELIVERY）

> 生成于回填完成后由 `make_delivery_report.py` 自动刷新；本文件为结构与路径权威说明。
> 数据文件 gitignore（/lhb/ /blockmargin/ /raw/），仓库只存代码/manifest/报告。

## 数据集总览

| # | 数据集 | 路径 | schema 文件 | 粒度 | 覆盖 | 来源 |
|---|---|---|---|---|---|---|
| ① | 龙虎榜席位 | `lhb/csv/lhb_seats.csv` | 见下 | 交易日×个股×原因×席位 | 2021-01-04→今 | 沪深交易所官方 |
| ① | 龙虎榜日度聚合 | `lhb/csv/lhb_daily_stock.csv` | 见下 | 交易日×个股×原因 | 同上 | 同上 |
| ② | 大宗交易 | `blockmargin/csv/block_trades.csv` | `BLOCK_META.json` | 交易日×笔（含买卖营业部） | 同上 | 同上 |
| ③ | 融资融券 | `blockmargin/csv/margin_daily.csv` | `MARGIN_META.json` | 交易日×标的 | 同上 | 同上 |

所有 CSV 为 UTF-8-SIG（Excel 直开），代码保留前导零，金额统一为元、股数统一为股。

## ① lhb_seats.csv 字段

`trade_date, exchange(SSE/SZSE), board(MAIN/STAR), code, name,
reason_code, reason_text, side(B/S), rank(1-5), seat_name,
is_institution, is_northbound, buy_amt, sell_amt(元),
abnormal_start, abnormal_end, source, raw_file`

- `lhb_daily_stock.csv`：日×股聚合，含 `inst_net`（机构净买）、`nb_net`（北向净买）等。
- `DATASET_META.json`：来源 meta（端点、抓取时间、行数、单位）。
- 证据链：`lhb/raw/` 原始响应只增不改；`backfill_state.json` 逐日状态。

## 质量门（gate）

- `lhb/crosscheck_report.json`：TDX 副本 81 事件（2026-05-26..08-31 窗口）
  vs 官方 CSV 逐席位对账；PASS 阈值：共享席位≥10、名称一致率≥99%、
  金额一致率≥97%（±0.1% 容差）。
- `collector/quality_audit.py`：完整性/单调性/构成审计
  （实测首批：金额排序违规 0/7447 榜）。

## 复现与运维

```powershell
# 全量重建（断点续跑；~1393 交易日）
python collector\lhb_backfill.py
python collector\block_margin_backfill.py block  sse
python collector\block_margin_backfill.py block  szse
python collector\block_margin_backfill.py margin sse
python collector\block_margin_backfill.py margin szse
# 归一化 + 验证
python collector\lhb_normalize.py;  python collector\block_normalize.py;  python collector\margin_normalize.py
python collector\lhb_crosscheck_tdx.py;  python collector\quality_audit.py
# 日常增量（盘后）
python collector\daily_incremental.py
```

硬规则（详见 docs/LHB_PIPELINE.md）：单实例锁；回填期间零并发 SZSE 请求；
熔断器 150s×2^n；SSE/SZSE 端点与坑位见 docs/BLOCK_MARGIN_ENDPOINTS.md。

## 已知边界

- **多日异常区间披露语义**：连续三日偏离类上榜（reason 1001/1002 等）的
  席位金额是**异常区间累计**（非单日）；数据保留 `abnormal_start/end`
  区间字段。外部对照：东方财富对同一事件显示单日化口径（抽验
  000007 2021-02-22：我方=SZSE 官方区间披露原样、EM 买卖总额差
  1.2%/3.5%，席位级一致）——以交易所披露（本数据集）为准。
- SZSE 两融 tab2 无 融资买入/偿还 的融券卖出/偿还列（rqmcl/rqchl 仅 SSE 有）。
- SSE 龙虎榜每席位仅主侧金额；SZSE 双侧金额齐。
- TDX 侧无 ①②③ 的长期历史（仅 10 事件滚动窗/快照）——官方源为主、
  TDX 为前向 PIT 与交叉验证。
- 2024 之前 SZSE 明细接口存在历史可比性（已抽验 2021）。

## 数字快照（回填完成后自动填充）

- lhb_seats 行数/天数：`__LHB_ROWS__` / `__LHB_DAYS__`
- block_trades 行数/天数：`__BLOCK_ROWS__` / `__BLOCK_DAYS__`
- margin_daily 行数/天数：`__MARGIN_ROWS__` / `__MARGIN_DAYS__`
- gate 结果：`__GATE__`
