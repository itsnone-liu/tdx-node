# TongdaXin Local Data Node Capability Probe

A reproducible capability audit for a local TongdaXin/TdxQuant node on Windows.

The repository contains probe scripts, sanitized raw responses, manifests, and the final capability report. It intentionally excludes the installed TongdaXin client, installer binaries, market caches, screenshots, logs, and saved-login state.

## Main result

The tested free account can provide local daily market data and several basic datasets through `tqcenter` and `127.0.0.1:17709`, but cannot access professional `GP52` ETF historical shares. Do not substitute `get_gb_info_by_date` for ETF historical shares: tests showed the current share snapshot repeated across all requested historical dates.

Read [`TDX_NODE_CAPABILITY_REPORT.md`](TDX_NODE_CAPABILITY_REPORT.md) for the complete matrix and evidence.

## Layout

- `collector/`: environment and generic TQ probes.
- `probes/`: focused read-only capability probes copied outside the installed client tree.
- `manifests/`: baselines, audits, the final machine-readable capability matrix, and the CSR-84 universe/capital/holders evidence.
- `raw/`: raw API/HTTP response samples used by the report.
- `automation/`: installer/UI inspection helpers and GitHub repo setup.
- `archivist/`: forward-PIT daily archivist (`daily_archive.py` + `run_daily.ps1`); registered as Windows scheduled task `tdx-archivist` (daily 20:30). Snapshots land in the git-ignored `archive/YYYYMMDD/` with per-artifact SHA256 manifests.
- `.learnings/`: operational findings and resolved errors.

## Follow-up evidence (2026-09-26, CSR-84 universe)

- `manifests/csr84_universe.json`: 84 frozen cases (baseline 1cabde8) in TDX code form.
- `manifests/capital_history_csr84.json`: share-capital change points 2021–2026 for all 84 stocks. Gate result: major (>=1%) share-count changes align with official effective dates (dividend/bonus events match exactly; spot-checked placement 000750.SZ 2023-11-17 and buyback-cancellation 000078.SZ 2024-08-20 both verified against official announcements). TDX change date semantics = effective/completion date, NOT announcement date — publication dates must come from an announcement index.
- `manifests/holders_coverage_csr84.json`: top-10 holders (gd + ltgd) content coverage across 2021–2026. Content-level only; holder snapshot dates are NOT publication dates.
- Permanent red line: ETF `get_gb_info_by_date` backfills the CURRENT share snapshot across history (unique value over 1250 days) — never use as historical ETF shares.

## Security

No saved credentials, account configuration, installed client files, vendor binaries, or mutable `T0002` state are committed. The probes rely on an already-running and already-authenticated client without reading credential storage.
