# LHB (龙虎榜) — 官方免费数据管线

数据类型①：龙虎榜席位级日度数据。**主数据源 = 沪深交易所官方免费接口**（TDX
免费版无法回溯历史，仅作前向 PIT 与交叉验证）。

覆盖：2021-01-04 → 今日（两所历史均实测可达 2021-01），交易日约 1393 天。

## 官方端点（Phase 0 已钉死并实测）

### 上交所 SSE（一天两发，席位内联返回，无需逐股明细）
| 用途 | URL | 参数 |
|---|---|---|
| 主板日榜+席位 | `http://query.sse.com.cn/marketdata/tradedata/queryAllTradeOpenDate.do` | `token=QUERY&tradeDate=YYYYMMDD&flag=1` |
| 科创板日榜+席位 | `http://query.sse.com.cn/marketdata/tradedata/queryKCBTradeInfo.do` | `tradeDate=YYYYMMDD&flag=2` |

- 必带 `Referer: http://www.sse.com.cn/`（否则 403）。
- 返回 `pageHelp.data[]`：每行 = (股票×原因) 的完整披露，**同时内联**
  `branchNameB/branchTxAmtB`（买方前五席位与金额，逗号拼接）和
  `branchNameS/branchTxAmtS`（卖方前五）。主板金额单位=元。
- 科创板行按 `txDirect` (B/S) 给 `deptNameB/deptTxAmtB` 或 `deptNameS/deptTxAmtS`，
  **金额单位=万元**（归一化时 ×10000）。
- 原因码 `refType` → 文本映射：`manifests/sse_reftype_map.json`（23 条，
  从官方页面 JS 提取）。数据自 2017-01-01 起统计（页面注）。

### 深交所 SZSE（日榜翻页 + 每股一次明细）
| 用途 | URL | 参数 |
|---|---|---|
| 每日榜单 | `https://www.szse.cn/api/report/ShowReport/data` | `SHOWTYPE=JSON&CATALOGID=1842_xxpl_after&TABKEY=tab1&txtStart=txtEnd=YYYY-MM-DD&PAGENO=N&random=0.x` |
| 席位明细 | 同上 | `CATALOGID=1842_detal&TABKEY=tab1,tab2&DQRQ=..&ZQDM=..&ZBDM=..`（参数取自榜单行 `bz` 字段内嵌链接） |

- 必带 `Referer: https://www.szse.cn/`。
- pagesize 固定 10，按 `PAGENO` 翻页（pagecount 在 metadata）。
- 明细 `tab2` 行：`mmlb`(买1..买5/卖1..卖5) `zsmc`(席位名) `mrje/mcje`
  (买/卖金额，**元**，每席位双侧金额都在)。
- 原因文本直接在榜单行 `plyy`；原因码 = `bz` 链接里的 `ZBDM`。

## 管线（collector/）

```
lhb_backfill.py     回填采集：逐交易日 SSE×2 + SZSE 榜单翻页 + 每股明细
                    （3 并发、共享限速 0.3s、指数退避重试、断点续跑、
                     单实例锁、--repair 文件驱动补洞、PARTIAL 状态语义）
prefetch_calendar.py 2021 上半年交易日预取（上证指数日K提取；TDX 本地
                    日历只到 2021-08-02 起）
lhb_normalize.py    raw → 统一 CSV（席位级 lhb_seats.csv + 日股聚合
                    lhb_daily_stock.csv + DATASET_META.json）
lhb_crosscheck_tdx.py  TDX 滚动窗口 vs 官方 CSV 的逐席位对账 gate
                    （名称一致率≥99%、金额一致率≥97%、容差±0.1%）
net_common.py       线程安全限速 HTTP 公共层
```

数据落盘：`lhb/raw/{sse_main,sse_star,szse_list,szse_detail}/*.json`
（**只增不改**，重复抓取跳过写入），状态 `lhb/backfill_state.json`
（合并写防多进程互踩）。

## 统一席位 schema（lhb_seats.csv）

`trade_date, exchange, board(MAIN/STAR), code(前导零保留), name,
reason_code, reason_text, side(B/S), rank(1-5), seat_name,
is_institution(含"机构专用"), is_northbound(沪/深股通专用),
buy_amt, sell_amt(元), abnormal_start/end, source, raw_file`

已知语义细节：
- SZSE 每席位双侧金额都在（买N 席位可有非零卖出）；SSE 每席位只挂主侧金额。
- 机构专用/沪股通专用/深股通专用 是席位名后缀，按子串识别。
- 科创板原始金额万元 → 归一化乘 10000。

## 运维注意（实测教训）

- **绝不要并发双开采集**：两个进程同打 SZSE 会触发 RemoteDisconnected
  风暴（2026-10-06 实测，单进程 3 并发 0.3s 限速稳定，双进程即挂）。
  已加单实例锁；`--repair` 绕过锁，也只能在主任务空闲时跑。
- 非交易日/无上榜日返回空 data 属正常（状态仍记 COMPLETE）。
- 全量回填 ~1393 交易日 × ~25s ≈ 9-10h；中断重跑自动续。
- gate 需官方回填覆盖 TDX 事件窗口（当前 TDX 副本事件在
  2026-05-26..2026-08-31）才能出对账结果。
