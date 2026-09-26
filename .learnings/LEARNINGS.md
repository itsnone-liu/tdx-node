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

## [LRN-20260926-005] tqcenter return-type traps

- **Category**: best_practice
- `get_divid_factors` returns a **pandas DataFrame** (dates on the index named `Date`, columns Type/Bonus/AllotPrice/ShareBonus/Allotment). Iterating it yields column-name strings and crashes with `AttributeError: 'str' object has no attribute 'get'`; an empty DataFrame silently "works", hiding the bug (688521 passed by luck).
- Correct handling: `dv.reset_index().to_dict('records')`, then stringify `Date` timestamps.
- Related trap: universe files that are objects (`{'codes': [...]}`) must be unwrapped before iterating — a raw `for x in dict` iterates keys and produces `codestr error` per key.
- `get_stock_list(market, list_type)`: only `list_type=1` works and already returns Code+Name dicts; `list_type=2/3` return empty lists silently.

## [LRN-20260926-006] PIT archive audit hardening

- **Category**: best_practice
- Provenance strings in manifests must be generated from the actual call, not hand-written beside it — v1.0 recorded `list_type=2` while calling with `list_type=1` after a bugfix; the metadata silently diverged (caught by external audit).
- A bare `status: complete` is meaningless for PIT archives: classify every fetch as SUCCESS_NONEMPTY / SUCCESS_EMPTY / FAILED (no-record ≠ fetch-failure) and gate a COMPLETE day on zero failures plus SHA re-verification.
- Client file-name prefixes differ per download kind (`etfpcf<code>_<date>`, `lhb<code>`, `lockshare<code>`, `holders<code>_<year>`); centralize them in one helper or misclassification follows.

## [LRN-20260926-007] frozen completeness contracts

- **Category**: best_practice
- A completeness counter derived from whatever loaded is not a contract: `try: codes = load() except: codes = []` lets a corrupt input silently shrink `expected` and still report COMPLETE. Freeze the expected cardinality independently (universe size + request formula) and hard-fail on any deviation — damage must be FAILED, never a smaller-but-green day.
- Grouped requests (N sub-fetches → 1 artifact) must keep request cardinality == completeness cardinality: either log every sub-request or count the group once with an internal tally that must sum to the group size.
