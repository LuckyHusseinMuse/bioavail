"""Apply db/schema.sql and load all reference data into Tiger Data (or a local TimescaleDB).

Reference tables are replaced in one transaction, so re-running is safe and leaves no half-loaded state.
User data (meals, alerts, chat) is never touched.

Run: python -m pipeline.load_db            (uses DATABASE_URL from backend/.env)
"""
from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "engine"))

from absorb_engine import load_reference_data  # noqa: E402
from absorb_engine.daily import reference_for  # noqa: E402

TEMPDATA = BACKEND / "TempData"
PROCESSED = BACKEND / "data" / "processed"
SCHEMA = BACKEND / "db" / "schema.sql"


def _rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _num(v):
    v = (v or "").strip() if isinstance(v, str) else v
    return None if v in ("", None) else float(v)


def _bool(v) -> bool:
    return str(v).strip().lower() == "true"


# table -> (source file, column builder)
REFERENCE_TABLES = {
    "foods": (PROCESSED / "foods.csv", lambda r: {
        "food_code": r["food_code"], "name": r["name"], "category": r["category"],
        "iron_mg": _num(r["iron_mg"]), "calcium_mg": _num(r["calcium_mg"]), "vitamin_c_mg": _num(r["vitamin_c_mg"]),
        "is_mfp": _bool(r["is_mfp"]), "mfp_fraction": _num(r["mfp_fraction"]) or 0, "is_drink": _bool(r["is_drink"]),
        "serving_g": _num(r["serving_g"]), "serving_label": r["serving_label"]}),
    "food_inhibitors": (PROCESSED / "food_inhibitors.csv", lambda r: {
        "food_code": r["food_code"], "beverage_class": r["beverage_class"] or None,
        "phytate_mg_per_100g": _num(r["phytate_mg_per_100g"]),
        "polyphenols_mg_per_serving": _num(r["polyphenols_mg_per_serving"]),
        "specific_modifier_id": r["specific_modifier_id"] or None, "data_status": r["data_status"]}),
    "absorption_baselines": (TEMPDATA / "absorption_baselines.csv", lambda r: {
        "baseline_id": r["baseline_id"], "nutrient_form": r["nutrient_form"],
        "value_pct": _num(r["baseline_absorption_value"]), "lower_pct": _num(r["baseline_absorption_lower"]),
        "upper_pct": _num(r["baseline_absorption_upper"]), "active": _bool(r["active"]),
        "human_verified": _bool(r["human_verified"])}),
    "absorption_modifiers": (TEMPDATA / "absorption_modifiers.csv", lambda r: {
        "modifier_id": r["modifier_id"], "name": r["modifier_name"], "nutrient_form": r["applicable_nutrient_form"],
        "direction": r["effect_direction"], "effect_value": _num(r["effect_value"]),
        "effect_lower": _num(r["effect_lower"]), "effect_upper": _num(r["effect_upper"]),
        "active": _bool(r["active"]), "human_verified": _bool(r["human_verified"])}),
    "interaction_rules": (TEMPDATA / "interaction_rules.csv", lambda r: {
        "rule_id": r["rule_id"], "trigger_entity": r["trigger_entity"], "conflict_group": r["conflict_group"],
        "modifier_id": r["modifier_id"] or None, "active": _bool(r["active"]), "human_verified": _bool(r["human_verified"])}),
    "engine_rule_evidence": (TEMPDATA / "engine_rule_evidence.csv", lambda r: {
        "rule_evidence_id": r["rule_evidence_id"], "engine_entity_type": r["engine_entity_type"],
        "engine_entity_id": r["engine_entity_id"], "paper_id": r["paper_id"] or None,
        "evidence_role": r["evidence_role"], "active": _bool(r["active"]), "human_verified": _bool(r["human_verified"])}),
    "evidence_papers": (TEMPDATA / "evidence_papers.csv", lambda r: {
        "paper_id": r["paper_id"], "title": r["title"], "year": int(r["year"]) if r["year"] else None,
        "citation_verified": _bool(r["citation_verified"])}),
    "engine_assumptions": (TEMPDATA / "engine_assumptions.csv", lambda r: {
        "assumption_id": r["assumption_id"], "name": r["name"], "value": _num(r["value"]), "active": _bool(r["active"])}),
    "validation_meals": (PROCESSED / "validation_meals.csv", lambda r: {
        "validation_id": r["validation_id"], "paper_id": r["paper_id"], "split": r["split"], "measure": r["measure"],
        "measured_value": _num(r["measured_value"])}),
}


def _insert(cur, table: str, rows: list[dict]) -> None:
    if not rows:
        return
    cols = list(rows[0].keys())
    sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})"
    cur.executemany(sql, [[Jsonb(r[c]) if c == "data" else r[c] for c in cols] for r in rows])


def schema_statements() -> list[str]:
    """Split schema.sql into statements (it has no function bodies, so splitting on ';' at line end is safe)."""
    text = "\n".join(line for line in SCHEMA.read_text(encoding="utf-8").splitlines() if not line.strip().startswith("--"))
    return [s.strip() for s in text.split(";\n") if s.strip().rstrip(";")]


def apply_schema(conn: psycopg.Connection) -> None:
    # Some TimescaleDB DDL (continuous aggregates, policies) must run outside a transaction block.
    conn.commit()
    previous = conn.autocommit
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            for stmt in schema_statements():
                cur.execute(stmt)
    finally:
        conn.autocommit = previous


def load(conn: psycopg.Connection) -> dict:
    counts = {}
    apply_schema(conn)

    ref = load_reference_data()
    with conn.transaction():
        with conn.cursor() as cur:
            for table, (path, build) in REFERENCE_TABLES.items():
                raw = _rows(path)
                rows = [{**build(r), "data": r} for r in raw]
                cur.execute(f"DELETE FROM {table}")
                _insert(cur, table, rows)
                counts[table] = len(rows)

            intakes = []
            for r in ref.reference_intakes:
                t = reference_for(ref, r["sex"], max(19, r["age_min"]))
                intakes.append({"sex": r["sex"], "age_min": r["age_min"], "age_max": r["age_max"],
                                "iron_rni_mg_day": r["iron_rni_mg_day"],
                                "absorbed_target_mg_day": t["absorbed_target_mg_day"],
                                "reference_day_fraction_pct": t["reference_day_fractional_pct"]})
            cur.execute("DELETE FROM reference_intakes")
            _insert(cur, "reference_intakes", intakes)
            counts["reference_intakes"] = len(intakes)
    return counts


def main() -> None:
    from dotenv import load_dotenv

    load_dotenv(BACKEND / ".env")
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL is not set (see backend/.env.example)")
    with psycopg.connect(url) as conn:
        counts = load(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT extversion FROM pg_extension WHERE extname = 'timescaledb'")
            version = cur.fetchone()[0]
    print(f"TimescaleDB {version}: schema applied")
    print(json.dumps(counts, indent=2))


if __name__ == "__main__":
    main()
