#!/usr/bin/env python3
"""Launch the signed TDX installer and inspect its UI without clicking Install."""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from pywinauto import Desktop

INSTALLER = r"D:\tdx-node\installers\new_tdx64_v773.exe"
OUT = Path(r"D:\tdx-node\logs\installer_ui.json")


def dump_control(c):
    try:
        r = c.rectangle()
        rect = [r.left, r.top, r.right, r.bottom]
    except Exception:
        rect = None
    try:
        text = c.window_text()
    except Exception:
        text = ""
    try:
        cls = c.class_name()
    except Exception:
        cls = ""
    try:
        ctrl_id = c.control_id()
    except Exception:
        ctrl_id = None
    return {"text": text, "class": cls, "control_id": ctrl_id, "rectangle": rect}


proc = subprocess.Popen([INSTALLER])
time.sleep(3)
windows = []
for backend in ("win32", "uia"):
    for w in Desktop(backend=backend).windows(process=proc.pid):
        item = {"backend": backend, "window": dump_control(w), "children": []}
        try:
            item["children"] = [dump_control(c) for c in w.descendants()]
        except Exception as exc:
            item["children_error"] = repr(exc)
        windows.append(item)
OUT.write_text(json.dumps({"pid": proc.pid, "windows": windows}, ensure_ascii=False, indent=2), encoding="utf-8")
print(OUT.read_text(encoding="utf-8"))
# Intentionally leave installer open for the next controlled step.
