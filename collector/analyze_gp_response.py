#!/usr/bin/env python3
"""Summarize TdxQuant get_gpjy_value raw JSON without altering it."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--output")
    args = ap.parse_args()
    src = Path(args.input)
    doc = json.loads(src.read_text(encoding="utf-8-sig"))
    response = doc.get("response") or {}
    summary = {"input": str(src), "status": doc.get("status"), "codes": {}}
    for code, fields in response.items():
        item = {"is_null": fields is None, "fields": {}}
        if isinstance(fields, dict):
            for field, rows in fields.items():
                rows = rows or []
                dates = [str(r.get("Date", "")) for r in rows if isinstance(r, dict)]
                item["fields"][field] = {
                    "rows": len(rows),
                    "first_date": min(dates) if dates else None,
                    "last_date": max(dates) if dates else None,
                    "duplicate_dates": sum(n - 1 for n in Counter(dates).values() if n > 1),
                    "sample_first": rows[:2],
                    "sample_last": rows[-2:],
                }
        summary["codes"][code] = item
    text = json.dumps(summary, ensure_ascii=False, indent=2, default=str)
    print(text)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
