# TDX CSR-84 证据报告：股本历史 · 十大股东 · Forward-PIT 归档

检测日期：2026-09-26
宇宙来源：stock-selector-v2 `phase_a/sample_selection.json`（冻结基线 `1cabde8`，84 案例 = G1:4 + G2/G3/G4/G5:20，multi-group=0）
工具链：隔离客户端 tdx-tq-v773 + tqcenter 1.1.0 + 免费账号

## 一、总股本/流通股本历史（E-MKT-04 / E-SEC-04 候选）

数据源：`get_gb_info_by_date`（股票侧；ETF 侧永久禁用，见红线）
证据：`manifests/capital_history_csr84.json`（逐股变化点+除权对账），原始逐日序列在 `archive/capital_history_raw/`（未入库）

覆盖：

| 组 | n | 最小行数 | 无变化股 | ≥1%总股本变化 | 除权匹配 |
|---|---|---|---|---|---|
| G1_complete_bull | 4 | 913 | 0 | 6 | 3 |
| G2_breakout_fail | 20 | 777 | 4 | 26 | 5 |
| G3_high_collapse | 20 | 826 | 0 | 27 | 12 |
| G4_quiet_then_go | 20 | 1240 | 4 | 31 | 3 |
| G5_sector_follower | 20 | 809 | 2 | 22 | 6 |
| 合计 | 84 | — | 10 | 112 | 29 |

- 窗口 2021-01-01..2026-09-24；实际序列普遍自 2021-08-02 起（=冻结窗口 w_start），6 只晚 IPO 股自动从上市日起，全覆盖无缺口。
- 变化点共 703：406 涉及总股本（294 个 <1% 微调 + 112 个 ≥1% 实质变动），297 个仅流通股本变动（中位幅度 0.25%，含解禁/回购等）。

### Gate 三层验证（全部通过）

1. **送转/配股内部一致性**：29 个变化点命中除权日；其中 27 个带送/转/配因子，**26 个实际比例与理论 (10+送+配)/10 误差 ≤2%**。唯一离群：002864.SZ 20260713（0.9894 vs 1.30）——疑似同期叠加回购注销类变动，列为已知差异。
2. **外部官方公告抽查（2/2 精确命中）**：
   - 000750.SZ 20231117 +17.30% ↔ [向特定对象发行A股股票上市公告书 2023-11-15](https://data.eastmoney.com/notices/detail/000750/AN202311151610990876.html)（新股上市生效日=TDX变化日）；
   - 000078.SZ 20240820 −4.35% ↔ [限制性股票回购注销完成公告 2024-08-20](https://data.eastmoney.com/notices/detail/000078/AN202408201639364401.html)（完成日=TDX变化日）。
3. **反向完整性**：33 个送转类除权事件中 7 个无邻近 ≥1% 股本变化（多为小额或数据取整），不构成方向性风险。

### 语义结论（升级前置声明）

**TDX 股本变化日 = 生效日/完成日（上市日、注销完成日、除权日），不是公告日。**
→ `market_cap(T) = price(T) × share_capital(T)` 在生效日语义下成立（BACKTEST_ONLY→CONTENT_VERIFIED）；
→ PIT 严格语义仍需公告日链（publication_date/available_date）由公告索引补齐，tdx-node 不承担此环节（分工边界 2026-09-26）。

## 二、十大股东 content coverage（E-STK-02 content source）

数据源：`download_file(type=1)` → `holders<code>_<year>.json`（gd=十大股东 + ltgd=十大流通股东，含排名/名称/持股数/比例）
证据：`manifests/holders_coverage_csr84.json`；规范化快照在 `archive/holders_csr84/`（未入库）

状态：**CONTENT_OK_PIT_PENDING**——文件内日期为持仓/快照日期；publication_date 未证明，禁止直接当 PIT 源。PIT 化路径 = TDX content × 官方公告索引 publication_date join。

（覆盖数字见 holders_coverage_csr84.json summary 段。）

覆盖实测（504 次下载零错误，2035 个快照日期）：

| 年份 | 有数据股票 | 快照数 | 其中含 ltgd |
|---|---|---|---|
| 2021 | 78/84（缺=晚IPO） | 354 | 321 |
| 2022 | 82/84 | 356 | 325 |
| 2023 | 84/84 | 375 | 337 |
| 2024 | 84/84 | 383 | 363 |
| 2025 | 84/84 | 374 | 347 |
| 2026（截至9月） | 84/84 | 193 | 177 |

- 每股快照数：min=15 / p25=23 / 中位=24 / max=35（≈每年4次，季报+期间披露节奏）。
- 五组均衡（组内每股最少 15–22 个快照），无组偏差。
- 内容字段：排名 pm、名称 name、持股数 cgsl、比例 cgbl；gd 与 ltgd 双表同日成对。

## 三、Forward-PIT daily archivist（已上线）

- 脚本：`archivist/daily_archive.py` + `run_daily.ps1`；计划任务 `tdx-archivist`（每日 20:30，Interactive）。
- 每日采集：ETF 全列表(31)、沪深300成份(23)、两融分类(56/57 标签未定)、ETF watchlist PCF(type=2)、84 案例当日股本快照、watchlist LHB(6)/解禁(7)、十大股东(1, 每周一)。
- 每件产物带 `retrieved_at/request/sha256/bytes` 写入 `archive/<YYYYMMDD>/manifest.json`（数据目录 git-ignored）；幂等，`--force` 重跑。
- 自启动链：17709 不通时自动拉起隔离客户端并等待就绪（依赖客户端自身记住登录，全程不触碰凭据）。

## 红线（永久）

1. ETF `get_gb_info_by_date` = 当前快照回填伪历史（510300/510050/159919 全程 unique_zgb=1）——永久禁用为 ETF 历史份额。
2. GP52/个股两融历史 = 付费墙（ErrorId=0 null），免费路线止损。
