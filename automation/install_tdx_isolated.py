#!/usr/bin/env python3
"""Drive the already-running signed TDX installer into an isolated folder."""
from __future__ import annotations

import json
import time
from pathlib import Path
from pywinauto import Application, Desktop

PID = 17104
TARGET = r"D:\tdx-node\tdx-tq-v773"
LOG = Path(r"D:\tdx-node\logs\isolated_install.json")

app = Application(backend="win32").connect(process=PID)
win = app.window(class_name="#32770")
win.wait("visible", timeout=15)
# This 32-bit custom installer exposes controls reliably by native HWND, while
# pywinauto's parent-scoped lookup may miss them under 64-bit Python.
from pywinauto.controls.hwndwrapper import HwndWrapper
edit = HwndWrapper(67596)
edit.set_edit_text(TARGET)
agreement = HwndWrapper(67638)
try:
    if agreement.get_check_state() == 0:
        agreement.click()
except Exception:
    agreement.click()
start = HwndWrapper(67598)
start.click()

records = []
for _ in range(180):
    time.sleep(1)
    wins = []
    for w in Desktop(backend="win32").windows(process=PID):
        try:
            wins.append({
                "title": w.window_text(),
                "class": w.class_name(),
                "texts": [c.window_text() for c in w.descendants() if c.window_text()],
            })
        except Exception:
            pass
    records.append({"t": len(records) + 1, "windows": wins, "target_exists": Path(TARGET).exists()})
    # Auto-ack only the installer's own informational OK dialogs; never accept path changes.
    for w in Desktop(backend="win32").windows(process=PID):
        try:
            if w.class_name() == "#32770" and w.window_text() != win.window_text():
                ok = w.child_window(control_id=1, class_name="Button")
                if ok.exists() and any(k in " ".join(c.window_text() for c in w.descendants()) for k in ("成功", "完成", "确定")):
                    ok.click()
        except Exception:
            pass
    try:
        if not app.is_process_running():
            break
    except Exception:
        break

LOG.write_text(json.dumps({"pid": PID, "target": TARGET, "records": records[-20:]}, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"target": TARGET, "exists": Path(TARGET).exists(), "last": records[-1] if records else None}, ensure_ascii=False, indent=2))
