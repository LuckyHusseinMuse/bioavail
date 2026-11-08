"""Run the validation report and write data/processed/validation_report.json.

Run: python -m pipeline.validate
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "engine"))

from absorb_engine import load_reference_data  # noqa: E402
from absorb_engine.validation import run_validation  # noqa: E402

OUT = BACKEND / "data" / "processed" / "validation_report.json"


def main() -> None:
    report = run_validation(load_reference_data())
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("Validation (relative change in non-haem absorption, percentage points)\n")
    for split, s in report["summary"].items():
        print(f"  {split:12} n={s.get('n')}  MAE={s.get('mae_pp')}  median={s.get('median_abs_error_pp')}  worst={s.get('worst')}")
    print("\n  id            split        measured  predicted  error  comparison")
    for r in report["rows"]:
        print(f"  {r['validation_id']:13} {r['split']:12} {r['measured_change_pct']:8.1f} {r['predicted_change_pct']:10.1f} "
              f"{r['error_pp']:6.1f}  {r['comparison']}")
    print(f"\n  skipped: {len(report['skipped'])} absolute rows (composition not extracted)")
    daily = dict(report["daily_cross_check"])
    refday = daily.pop("_reference_day")
    print(f"\nReference day: eaten {refday['iron_mg']} mg, absorbed {refday['absorbed_mg']} mg, "
          f"fraction {refday['fractional_pct']}%, share of potential {refday['share_of_potential_pct']}%, conflicts {refday['conflicts']}")
    print("Daily cross-check (woman 19-50; target = 14.8 mg x reference-day fraction)")
    for name, d in daily.items():
        print(f"  {name:22} eaten {d['iron_mg']:5.1f} mg  absorbed {d['absorbed_mg']:.2f} mg  fraction {d['fractional_pct']}%  "
              f"share of potential {d['share_of_potential_pct']}%  share of target {d['absorbed_share_of_target']}  "
              f"conflicts {d['conflicts']}")
    print(f"\nWrote {OUT.relative_to(BACKEND)}")


if __name__ == "__main__":
    main()
