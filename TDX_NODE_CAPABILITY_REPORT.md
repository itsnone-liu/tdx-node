# 通达信本地数据节点能力检测报告

检测日期：2026-09-26
节点系统：Windows 10 Pro 64-bit（build 19045）
原始客户端：`D:\new_tdx`
隔离 TQ 客户端：`D:\tdx-node\tdx-tq-v773`（通达信金融终端 V7.73 64 位，TQCenter 1.1.0）

## 1. 结论摘要

本机可以作为通达信本地行情节点，稳定提供日线行情、除权事件、股票股本、ETF列表/跟踪关系以及若干公开文件下载；Python 可通过 `tqcenter` 或本地 HTTP `127.0.0.1:17709` 读取。

但是，当前账号是免费权限，客户端在进入“系统 → 专业财务数据”时明确提示：

> 专业财务数据需要购买普及版或以上版本

因此，ETF 历史份额/规模 `GP52` 和融资融券历史 `GP03/GP11/GP12/GP13` 当前不可用。原始 DLL 对 GP52 返回 `ErrorId=0` 但 `Value=null`；这不是 Python 封装错误，也不是缺少普通 `vipdoc` K线。

最重要的回测红线：**不得用 `get_gb_info_by_date` 替代 ETF 历史份额。** 对 510300、510050、159919，该接口虽然生成 1250 个历史交易日，但每一天都重复当前份额，属于“当前快照铺满历史”，会造成严重前视偏差。

## 2. 分阶段检测结果

### W0：原始节点基线

- `D:\new_tdx\TdxW.exe` SHA256：`F5F2E6025A4D80BB1AFBCB2A51C753D3C1909E09AA9D1BC8F7C3B701B081F74C`
- SH 日线文件：4,879
- SZ 日线文件：4,369
- BJ 日线文件：350
- 基线时无 `PYPlugins`、无 `tqcenter.py`、无 17709 监听。
- 检测结束后重新计算原客户端哈希，仍完全一致，原安装未被修改。

### W1：隔离安装和连接

- 官方 V7.73 64位安装在 `D:\tdx-node\tdx-tq-v773`。
- `tqcenter.py` 版本：1.1.0。
- 自动登录后 `127.0.0.1:17709` 由隔离客户端监听。
- 未读取、复制或管理保存的账号密码，只依赖客户端自身的自动登录状态。

### W2：GP52 和专业股票交易数据

实测代码：510300.SH、510050.SH、159919.SZ。
实测字段：GP51、GP52。
原始 DLL 返回：`ErrorId=0`，但三只证券的 `Value` 均为 `null`。

已排除：

1. `tqcenter` 未初始化；
2. 客户端未登录；
3. 17709 未就绪；
4. Python 封装过滤结果；
5. 普通 K 线未复制；
6. `refresh_cache(market="AG", force=True)` 未执行。

最终根因是当前账号无“专业财务数据/股票数据包”权限。

## 3. 能力矩阵

| 数据集 | 状态 | 时间语义/覆盖 | 回测判断 |
|---|---|---|---|
| 沪深京日线 OHLCV | 可用 | 历史交易日序列；样本约 2021-08 至 2026-09 | 可用，需明确复权政策 |
| 本地 HTTP 行情 | 可用 | 600519 最近5日与本地历史一致 | 可作为本机服务接口 |
| 分红送配/除权事件 | 可用 | 600519 在 2021–2026 返回10条 | 可用于复权；不含公告时点 |
| 股票股本历史 | 可用但需校验 | 600519 返回1250日、3个不同总股本值 | 股票可用；应核对变更日 |
| ETF历史份额/规模 GP52 | 当前账号不可用 | 返回 null；需普及版或以上 | 不可用 |
| ETF股本接口冒充历史份额 | 危险伪历史 | 三只ETF 1250日均只有1个唯一值 | 严禁用于回测 |
| ETF PCF/申赎清单 | 可下载 | 指定日汇总头信息，不是历史份额 | 只能前瞻式逐日归档 |
| ETF列表 | 当前快照可用 | 1,729只 | 有幸存者偏差，不可直接回溯历史池 |
| 沪深300跟踪ETF | 当前快照可用 | 30只 | 同上 |
| 两融余额历史 GP03等 | 当前账号不可用 | 与GP52共用专业数据权限 | 不可用 |
| 两融标的池 | 当前分类可查，标签待确认 | 分类代码56/57分别3979/4460只 | 仅当前快照；不可作为历史标的池 |
| 十大股东 | 可下载 | 600519 2025年文件含7个日期快照 | 必须保存公告/获取时点，防前视 |
| 龙虎榜 | 最近文件可下载 | 688318样本为空，无近期记录 | 未证明完整历史，不批准全历史回测 |
| 限售解禁 | 文件可下载 | 688318返回2023-04-27实施事件 | 需外部补公告时点 |
| 涨跌停/除权日专用API | 接口存在 | 本轮未证明完整历史覆盖 | 暂不批准完整回测使用 |
| GUI 自动化 | 可用作控制面 | 菜单命令、登录、下载、恢复 | 不作为数据面 |

## 4. ETF 历史份额的关键语义验证

### 4.1 GP52 官方语义

- ETF基金规模数据；
- 基金份额：万份；
- 基金规模：万元。

### 4.2 免费股本接口为什么不能替代

`get_gb_info_by_date` 的实测结果：

| 代码 | 日期行数 | Zgb唯一值数 | 全区间值 |
|---|---:|---:|---:|
| 510300.SH | 1,250 | 1 | 23,904,487,424 |
| 510050.SH | 1,250 | 1 | 7,167,366,656 |
| 159919.SZ | 1,250 | 1 | 6,566,617,088 |

510300 最新 PCF 的 `jzrfe=2,390,448.77` 万份，约等于 23,904,487,700 份，与上述“历史”值对应。这证明接口把当前份额扩展到所有请求日期，而非提供逐日真实历史。

## 5. 17709 HTTP 调用方式

官方协议不是标准 JSON-RPC/MCP 握手。正确请求形态：

```json
{
  "id": 1,
  "method": "get_market_data",
  "params": {
    "stock_list": ["600519.SH"],
    "count": 5,
    "dividend_type": "none",
    "period": "1d"
  }
}
```

发送到：

```text
POST http://127.0.0.1:17709/
```

兼容性注意：HTTP 转发 `get_gpjy_value` 时，公开 Python 参数名 `field_list` 没有被转换，底层会报 `json has no table_list`；HTTP 方式需传 `table_list`。即使正确传入 `table_list=["GP52"]`，当前账号仍返回 null。

## 6. 数据工程建议

### 推荐架构

1. **数据面**：Python 优先读取 `.day`、`tqcenter` 或 17709 HTTP；
2. **控制面**：Windows 通达信负责自动登录、刷新/下载和异常恢复；
3. **GUI**：只在登录、下载或恢复时使用，不抓屏取数据；
4. **原始数据**：每次采集保存原始 JSON、请求参数、获取时间和哈希；
5. **时间语义**：分别保存 `announcement_date`、`effective_date`、`event_date`、`retrieved_at`；
6. **历史成份/资格池**：不得把当前 ETF 列表、当前两融池倒灌到历史；
7. **ETF份额**：若策略必须使用，选择以下一种：
   - 购买普及版或更高权限后复测 GP52；
   - 使用交易所/基金公司/可靠第三方的点时历史数据；
   - 从现在起每日归档 PCF/官方份额快照，但不得声称补齐过去历史。

### GUI 命令证据

从签名客户端菜单资源直接解析：

- 系统 → 盘后数据下载：命令 ID `9279`；
- 系统 → 专业财务数据：命令 ID `9264`。

专业数据窗口是嵌入 Chromium，自绘内容不稳定且 UIA 暴露有限；因此命令 ID、窗口标题和端口就绪检查比视觉点击更可靠。

## 7. 交付文件

### 核心探针

- `D:\tdx-node\collector\probe_tdx_environment.py`
- `D:\tdx-node\collector\probe_tq.py`
- `D:\tdx-node\tdx-tq-v773\PYPlugins\user\tdx_probe_gp52.py`
- `D:\tdx-node\tdx-tq-v773\PYPlugins\user\tdx_probe_raw_pro.py`
- `D:\tdx-node\tdx-tq-v773\PYPlugins\user\tdx_probe_free_capabilities.py`
- `D:\tdx-node\tdx-tq-v773\PYPlugins\user\tdx_probe_etf_gb.py`
- `D:\tdx-node\tdx-tq-v773\PYPlugins\user\tdx_probe_market_categories.py`

### 关键证据

- `D:\tdx-node\manifests\w0_baseline_20260926.json`
- `D:\tdx-node\manifests\w1_install.json`
- `D:\tdx-node\manifests\gp52_permission_finding.json`
- `D:\tdx-node\manifests\etf_gb_lookahead_audit.json`
- `D:\tdx-node\manifests\downloaded_files_audit.json`
- `D:\tdx-node\manifests\final_capability_matrix.json`
- `D:\tdx-node\raw\raw_pro_gp51_gp52.json`
- `D:\tdx-node\raw\http_17709_probe.json`
- `D:\tdx-node\raw\http_17709_gp52_table_list.json`
- `D:\tdx-node\raw\tq_free_capabilities.json`
- `D:\tdx-node\raw\tq_etf_gb_history.json`

## 8. 最终实施判断

- **本机通达信可作为 Python 策略的本地行情与基础数据节点。**
- **当前免费账号不能提供可信 ETF 历史份额 GP52。**
- **如果 ETF 历史份额是硬性回测因子，必须升级权限或引入独立点时数据源。**
- **Computer Use/GUI 只保留为 Windows 节点控制面降级方案，不进入策略数据面。**
