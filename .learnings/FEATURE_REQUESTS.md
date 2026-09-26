# Feature Requests

Capabilities requested by the user.

---

## [FEAT-20260926-001] tdx-data-node

**Logged**: 2026-09-26T09:45:00+08:00
**Priority**: high
**Status**: in_progress
**Area**: backend

### Requested Capability
Use the local Windows TongdaXin client as a reproducible data source for stock-strategy backtesting, including ETF historical shares and other Phase-B datasets.

### User Context
The user needs auditable historical inputs for Python strategy backtests and prefers local/free TDX capabilities over fragile web scraping.

### Complexity Estimate
complex

### Suggested Implementation
Probe in order: vipdoc files, local TQ/tqcenter, optional localhost HTTP, then GUI maintenance fallback; emit raw samples, Parquet, manifests and a capability matrix.

### Metadata
- Frequency: first_time
- Related Features: project-916 Python backtest library

---
