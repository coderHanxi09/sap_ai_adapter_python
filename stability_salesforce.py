"""
Stability test for the Salesforce mapping flow.

Runs the same input (test_data/salesforce/sf_account_renamed.csv) through
map_to_sap with source_system="salesforce" eight times and measures how
deterministic the output is across runs.

For each run we save the full result JSON to
actual_outputs/salesforce/stability/run_<N>.json and we compare:
  - exact equality of the canonical JSON serialization
  - which top-level BusinessPartner fields differ across runs

The aggregate report is written to
evaluation_results/salesforce_stability.json.

Usage:
  python stability_salesforce.py              # run all 8 (skip existing with --resume)
  python stability_salesforce.py --resume   # continue from missing runs only
  python stability_salesforce.py --analyze-only  # score existing run_*.json files
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Set

from parser import parse_file
from ai_mapper import map_to_sap


BASE_DIR = Path(__file__).resolve().parent
INPUT_PATH = BASE_DIR / "test_data" / "salesforce" / "sf_account_renamed.csv"
RUN_OUTPUT_DIR = BASE_DIR / "actual_outputs" / "salesforce" / "stability"
RESULTS_DIR = BASE_DIR / "evaluation_results"

NUM_RUNS = 8
MAX_ATTEMPTS = 5
BACKOFF_SECONDS = [15, 30, 60, 120]


def map_with_retry(parsed, label: str):
    """Call map_to_sap with backoff for transient 5xx / 429 errors."""
    last_exc: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return map_to_sap(
                parsed,
                target_schema="BusinessPartner",
                source_system="salesforce",
            )
        except Exception as exc:
            last_exc = exc
            if attempt == MAX_ATTEMPTS:
                break
            wait = BACKOFF_SECONDS[min(attempt - 1, len(BACKOFF_SECONDS) - 1)]
            print(
                f"[{label}] attempt {attempt} failed: {exc!r}. "
                f"retrying in {wait}s...",
                file=sys.stderr,
                flush=True,
            )
            time.sleep(wait)
    raise last_exc  # type: ignore[misc]


def canonicalize(obj: Any) -> str:
    """Stable JSON serialization for equality checking."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


def collect_top_level_fields(result: Any) -> List[Set[str]]:
    """
    For a list-shaped result of BusinessPartner wrappers, return one
    set of BusinessPartner field names per row. Falls back gracefully
    if the structure is not as expected.
    """
    out: List[Set[str]] = []
    items = result if isinstance(result, list) else [result]
    for item in items:
        if isinstance(item, dict) and isinstance(item.get("BusinessPartner"), dict):
            bp = item["BusinessPartner"]
            out.append({k for k, v in bp.items() if v not in (None, [], {})})
        elif isinstance(item, dict):
            out.append(set(item.keys()))
        else:
            out.append(set())
    return out


def load_existing_runs() -> Dict[int, Any]:
    """Load run_<N>.json files that already exist on disk."""
    found: Dict[int, Any] = {}
    for i in range(1, NUM_RUNS + 1):
        path = RUN_OUTPUT_DIR / f"run_{i}.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                found[i] = json.load(f)
    return found


def analyze_runs(runs: List[Any], run_indices: List[int]) -> Dict[str, Any]:
    canonical_runs = [canonicalize(r) for r in runs]
    unique_outputs = set(canonical_runs)
    fully_identical = len(unique_outputs) == 1

    per_run_field_sets = [collect_top_level_fields(r) for r in runs]

    diff_fields_per_row: List[Dict[str, Any]] = []
    if per_run_field_sets:
        max_rows = max(len(s) for s in per_run_field_sets)
        for row_idx in range(max_rows):
            field_sets_for_row: List[Set[str]] = []
            for run_fields in per_run_field_sets:
                if row_idx < len(run_fields):
                    field_sets_for_row.append(run_fields[row_idx])
                else:
                    field_sets_for_row.append(set())
            union_fields = set().union(*field_sets_for_row)
            intersection_fields = (
                set.intersection(*field_sets_for_row) if field_sets_for_row else set()
            )
            differing = sorted(union_fields - intersection_fields)
            diff_fields_per_row.append({
                "row_index": row_idx,
                "always_present_fields": sorted(intersection_fields),
                "sometimes_missing_fields": differing,
            })

    return {
        "input_file": str(INPUT_PATH),
        "num_runs_target": NUM_RUNS,
        "completed_runs": len(runs),
        "run_indices": run_indices,
        "unique_outputs": len(unique_outputs),
        "fully_identical": fully_identical,
        "row_field_diffs": diff_fields_per_row,
        "status": "complete" if len(runs) == NUM_RUNS else "partial",
    }


def print_summary(report: Dict[str, Any]) -> None:
    print("\n=== Stability summary ===")
    print(f"target runs:        {report['num_runs_target']}")
    print(f"completed runs:     {report['completed_runs']} {report['run_indices']}")
    print(f"status:             {report['status']}")
    print(f"unique outputs:     {report['unique_outputs']}")
    print(f"fully identical:    {report['fully_identical']}")
    for row in report["row_field_diffs"]:
        print(
            f"  row {row['row_index']}: "
            f"sometimes-missing top-level BP fields = {row['sometimes_missing_fields']}"
        )


def save_report(report: Dict[str, Any]) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "salesforce_stability.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nsaved -> {out_path}")
    return out_path


def run_mapper(resume: bool) -> None:
    print(f"Loading: {INPUT_PATH}")
    with open(INPUT_PATH, "rb") as f:
        parsed = parse_file(INPUT_PATH.name, f.read())

    RUN_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for i in range(1, NUM_RUNS + 1):
        out_path = RUN_OUTPUT_DIR / f"run_{i}.json"
        if resume and out_path.exists():
            print(f"\n--- run {i}/{NUM_RUNS} --- already exists, skipping")
            continue

        print(f"\n--- run {i}/{NUM_RUNS} ---")
        result = map_with_retry(parsed, label=f"run_{i}")

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"saved -> {out_path}")


def main() -> None:
    parser_ = argparse.ArgumentParser()
    parser_.add_argument(
        "--resume",
        action="store_true",
        help="skip runs whose run_<N>.json already exists",
    )
    parser_.add_argument(
        "--analyze-only",
        action="store_true",
        help="analyze existing run_*.json files without calling the API",
    )
    args = parser_.parse_args()

    if not args.analyze_only:
        run_mapper(resume=args.resume)

    existing = load_existing_runs()
    if not existing:
        print("No run outputs found. Run the mapper first.", file=sys.stderr)
        sys.exit(1)

    indices = sorted(existing.keys())
    runs = [existing[i] for i in indices]
    report = analyze_runs(runs, indices)
    print_summary(report)
    save_report(report)

    if report["status"] != "complete":
        missing = [i for i in range(1, NUM_RUNS + 1) if i not in existing]
        print(f"\nMissing runs: {missing}")
        print("Resume later with: python stability_salesforce.py --resume")
        sys.exit(0 if args.analyze_only else 1)


if __name__ == "__main__":
    main()
