# Errors

Command failures and integration errors.

---

## [ERR-20260926-001] powershell-foreach-pipeline

**Logged**: 2026-09-26T09:45:00+08:00
**Priority**: low
**Status**: resolved
**Area**: infra

### Summary
PowerShell parser rejected a pipeline placed directly after a foreach statement.

### Error
```
An empty pipe element is not allowed.
```

### Context
A HEAD-request result was emitted from `foreach (...) {...} | Format-Table` in a single statement.

### Suggested Fix
Accumulate objects in `$results` inside the loop, then pipe `$results` after the loop. The retry succeeded.

### Metadata
- Reproducible: yes
- Related Files: none

### Resolution
- **Resolved**: 2026-09-26T09:46:00+08:00
- **Notes**: Rewritten with a result array and verified all three official URLs.

---

## [ERR-20260926-002] powershell-format-hex-count

**Logged**: 2026-09-26T09:50:00+08:00
**Priority**: low
**Status**: resolved
**Area**: infra

### Summary
Windows PowerShell 5.1 `Format-Hex` does not support the newer `-Count` parameter.

### Error
```
A parameter cannot be found that matches parameter name 'Count'.
```

### Context
The command attempted to inspect the first 256 bytes after Authenticode verification. Signature verification itself completed successfully.

### Suggested Fix
Use `Get-Content -Encoding Byte -TotalCount 256` or read a bounded byte array instead of `Format-Hex -Count` on PowerShell 5.1.

### Metadata
- Reproducible: yes
- Related Files: none

### Resolution
- **Resolved**: 2026-09-26T09:50:00+08:00
- **Notes**: Installer format identification was moved to 7-Zip listing; no security conclusion depended on Format-Hex.

---
