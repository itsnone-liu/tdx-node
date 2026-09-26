# TongdaXin Local Data Node Capability Probe

A reproducible capability audit for a local TongdaXin/TdxQuant node on Windows.

The repository contains probe scripts, sanitized raw responses, manifests, and the final capability report. It intentionally excludes the installed TongdaXin client, installer binaries, market caches, screenshots, logs, and saved-login state.

## Main result

The tested free account can provide local daily market data and several basic datasets through `tqcenter` and `127.0.0.1:17709`, but cannot access professional `GP52` ETF historical shares. Do not substitute `get_gb_info_by_date` for ETF historical shares: tests showed the current share snapshot repeated across all requested historical dates.

Read [`TDX_NODE_CAPABILITY_REPORT.md`](TDX_NODE_CAPABILITY_REPORT.md) for the complete matrix and evidence.

## Layout

- `collector/`: environment and generic TQ probes.
- `probes/`: focused read-only capability probes copied outside the installed client tree.
- `manifests/`: baselines, audits, and the final machine-readable capability matrix.
- `raw/`: raw API/HTTP response samples used by the report.
- `automation/`: installer/UI inspection helpers; GUI is a control-plane fallback only.
- `.learnings/`: operational findings and resolved errors.

## Security

No saved credentials, account configuration, installed client files, vendor binaries, or mutable `T0002` state are committed. The probes rely on an already-running and already-authenticated client without reading credential storage.
