# Archivist 停机复盘：20260928–20261004

## 现象

计划任务 `tdx-archivist`（每日 20:30）自 2026-09-28 起连续 8 天 fatal FAILED：

```
fatal: RuntimeError: client plane 127.0.0.1:17709 not available and could not be started
expected_requests: 0   （契约未加载，非数据为空）
run exit 2
```

最后一次成功运行：2026-09-27（COMPLETE 53/53，46 非空 7 空 0 败）。

## 根因

TDX 客户端（TdxW.exe）的**自动登录失效**。客户端启动后停在登录对话框
（#32770，564×428：账号 13771500926 与密码已记住并预填，只差点击"登 录"），
主界面未进入 → PYPlugins/tqcenter 的 17709 HTTP plane 永远不启动 →
archivist v1.2.0 的 `ensure_client()` 等 240 秒后放弃，如实落 FAILED。

- 2026-09-26/27 自动登录正常（9-27 由 archivist 拉起客户端后 plane 正常打开）。
- 2026-10-05 实测：交互登录成功后**重启客户端自动登录依然失效**（登录框重现），
  排除"登录一次即可恢复"的可能 → 需要机制性兜底，而非一次性人工登录。

## 修复（archivist v1.3.0，2026-10-05）

`ensure_client()` 增加登录自愈：客户端拉起后先给自带自动登录 60 秒；
plane 未开则枚举该进程可见的 #32770 登录框（尺寸合理性 300–900×250–700），
在窗口矩形的相对坐标 (0.50, 0.834) 处模拟单击"登 录"（实测按钮中心：
dialog 564×428 → 相对 (282,357) → 屏幕 (960,662)），最多两次，总预算 240 秒不变。

- 不读取、不复制、不输入任何凭据——对话框自带的"记住密码"是唯一凭据来源，
  代码只替用户按下按钮（用户 2026-10-05 认可此交互方式）。
- 端到端验证：杀掉客户端 → `ensure_client()` 实测输出
  `login dialog detected (564x428 at 678,306); clicked 登录 at (960,662)`
  → plane 打开，返回 listener pid。今晚 20:30 计划任务预期自愈。
- 前置条件不变：计划任务 Interactive only（桌面需处于登录解锁状态）。

## 数据缺口（诚实记录）

| 日期 | 当日状态 | 缺口 |
|---|---|---|
| 20260928（周一，交易日，holders 日） | FAILED | 全部 137 项缺失（含 holders） |
| 20260929（周二，交易日） | FAILED | 53 项快照缺失 |
| 20260930（周三，交易日） | FAILED | 53 项快照缺失 |
| 20261001–04（国庆假期+周日） | FAILED | 名义缺口，实际无新数据 |

- **不可恢复**：市场列表/沪深300/两融分类/gb_today/LHB/解禁为"当日最新快照"
  类源，服务器不提供历史 → 3 个交易日的快照永久缺失，保留 FAILED manifest 为证。
- **已恢复**：ETF PCF 为按日期下载（`download_file(code, down_time, 2)`），
  服务器仍提供历史日期 → 3 天 × 8 只 = 24/24 全部补回，存于
  `archive/backfill_pcf_20260928_0930/`（含 manifest/sha256；不写入当日目录，
  以免破坏 FAILED 日志的 orphan 不变量）。补拉脚本：
  `jobs/backfill_pcf_20260928_0930.py`。
- **holders 节奏**：丢失 9-28 一个周采样点；20261005（周一）holders 已正常归档
  （137/137，130 非空），周节奏恢复。

## 2026-10-05 恢复验证

手动登录 + `python archivist/daily_archive.py`：

```
{"date": "20261005", "status": "COMPLETE", "contract_met": true,
 "expected_requests": 137, "successful_requests": 137,
 "success_nonempty": 130, "success_empty": 7, "failed_requests": 0,
 "sha_verified": 130, "orphan_files": 0, "missing_files": 0}
```

（10-05 处于国庆假期，7 个 EMPTY 为诚实空值：当日无 PCF 等新数据。）
