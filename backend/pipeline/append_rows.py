"""Append-only helper for the curated CSVs in backend/TempData.

Existing rows are never touched. Aborts if a column is unknown or an ID already exists,
so re-running a batch is safe (it stops before writing anything).
"""
from __future__ import annotations

import csv
import sys
from datetime import datetime
from pathlib import Path

TEMPDATA = Path(__file__).resolve().parents[1] / "TempData"


def common(engine_version: str = "0.2") -> dict:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    return {"engine_version": engine_version, "active": "True", "human_verified": "False",
            "created_at": now, "updated_at": now}


def append(name: str, id_col: str, rows: list[dict]) -> None:
    path = TEMPDATA / name
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames
        existing = {r[id_col] for r in reader}
    for r in rows:
        extra = set(r) - set(header)
        if extra:
            sys.exit(f"{name}: unknown columns {extra}")
        if r[id_col] in existing:
            sys.exit(f"{name}: {r[id_col]} already exists, nothing written")
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header, lineterminator="\n")
        for r in rows:
            w.writerow({**{k: "" for k in header}, **r})
    print(f"{name}: appended {len(rows)} rows")
