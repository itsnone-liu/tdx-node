# Learnings

Corrections, insights, and knowledge gaps captured during development.

**Categories**: correction | insight | knowledge_gap | best_practice

---

## [LRN-20260926-001] TQ professional-data permission gate

- **Category**: insight
- `get_gpjy_value` can return `ErrorId=0` with per-security `null` values when the account cannot download the required professional stock-data package.
- Copying `vipdoc` and calling `refresh_cache(market="AG", force=True)` do not supply GP03/GP51/GP52.
- The authoritative capability check is the client command “系统 → 专业财务数据”; this account displayed “专业财务数据需要购买普及版或以上版本”.

## [LRN-20260926-002] ETF share-capital false history

- **Category**: correction
- `get_gb_info_by_date` is valid enough for ordinary-equity share-capital testing, but is not a substitute for ETF GP52 history.
- For 510300, 510050 and 159919 it returned 1,250 historical dates with exactly one unique `Zgb/Ltgb` value: the current ETF share count repeated backward.
- Always test historical fields for value variation and cross-check against an independently dated snapshot before approving them for backtests.

## [LRN-20260926-003] TQ local HTTP protocol

- **Category**: insight
- Port 17709 uses a simplified POST body `{id, method, params}`, not a standard MCP/JSON-RPC initialize/tools flow.
- For `get_gpjy_value`, the HTTP dispatcher requires the bottom-layer key `table_list`; sending the public Python wrapper key `field_list` produces `ErrorId=10` (`json has no table_list`).

## [LRN-20260926-004] GUI command discovery

- **Category**: best_practice
- Signed `TdxW.exe` menu resources can be loaded read-only to recover stable menu command IDs; this was more reliable than visual-model menu guessing or coordinate clicks.
- Verified IDs: 9279 = 盘后数据下载; 9264 = 专业财务数据.
- Treat GUI as control-plane fallback; embedded Chromium download pages expose little useful UIA structure.
