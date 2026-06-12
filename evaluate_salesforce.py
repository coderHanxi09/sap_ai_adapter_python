"""
Field-level evaluation for the Salesforce scenario.

Reads expected_outputs/salesforce/<case>_expected.json and the matching
actual_outputs/salesforce/<case>_actual.json, flattens both into
dot-paths and reports per-case accuracy plus the list of mismatched
fields. Aggregated results are written to
evaluation_results/salesforce_evaluation.json.

Comparison rules:
- Only fields that are present (and non-None) in EXPECTED are scored.
- Fields with None in expected are ignored (treated as "don't care").
- Lists are compared element-wise by index.
- Strings are compared after trim + lowercase to be a bit forgiving.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


BASE_DIR = Path(__file__).resolve().parent
EXPECTED_DIR = BASE_DIR / "expected_outputs" / "salesforce"
ACTUAL_DIR = BASE_DIR / "actual_outputs" / "salesforce"
RESULTS_DIR = BASE_DIR / "evaluation_results"

CASES = [
    "sf_account_standard",
    "sf_contact_standard",
    "sf_account_renamed",
    "sf_account_uk_customer",
    "sf_account_china_standard",
    "sf_contact_japan",
    "sf_account_partner",
    "sf_account_sparse_renamed",
]


# -------------------------
# Flattening
# -------------------------
def flatten(value: Any, prefix: str = "") -> Dict[str, Any]:
    """Flatten nested dicts/lists into {dot.path: leaf_value}."""
    flat: Dict[str, Any] = {}

    if isinstance(value, dict):
        for k, v in value.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            flat.update(flatten(v, key))
        return flat

    if isinstance(value, list):
        for i, v in enumerate(value):
            key = f"{prefix}[{i}]"
            flat.update(flatten(v, key))
        return flat

    flat[prefix] = value
    return flat


# -------------------------
# Comparison
# -------------------------
def values_equal(expected: Any, actual: Any) -> bool:
    if expected is None:
        return True

    if isinstance(expected, str) and isinstance(actual, str):
        return expected.strip().lower() == actual.strip().lower()

    if isinstance(expected, bool) or isinstance(actual, bool):
        return expected == actual

    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return float(expected) == float(actual)

    return expected == actual


def evaluate_case(case_name: str) -> Dict[str, Any]:
    expected_path = EXPECTED_DIR / f"{case_name}_expected.json"
    actual_path = ACTUAL_DIR / f"{case_name}_actual.json"

    if not expected_path.exists():
        return {
            "case_name": case_name,
            "status": "missing_expected",
            "expected_path": str(expected_path),
        }

    if not actual_path.exists():
        return {
            "case_name": case_name,
            "status": "missing_actual",
            "actual_path": str(actual_path),
        }

    with open(expected_path, "r", encoding="utf-8") as f:
        expected = json.load(f)
    with open(actual_path, "r", encoding="utf-8") as f:
        actual = json.load(f)

    flat_expected = flatten(expected)
    flat_actual = flatten(actual)

    mismatches: List[Dict[str, Any]] = []
    correct = 0
    total = 0

    for path, exp_value in flat_expected.items():
        if exp_value is None:
            continue
        total += 1
        act_value = flat_actual.get(path)
        if values_equal(exp_value, act_value):
            correct += 1
        else:
            mismatches.append({
                "field": path,
                "expected": exp_value,
                "actual": act_value,
            })

    accuracy = correct / total if total else 0.0

    return {
        "case_name": case_name,
        "status": "ok",
        "total_fields": total,
        "correct_fields": correct,
        "accuracy": round(accuracy, 4),
        "mismatches": mismatches,
    }


# -------------------------
# Pretty printing
# -------------------------
def print_summary(rows: List[Dict[str, Any]]) -> None:
    print("\n=== Salesforce evaluation summary ===")
    header = f"{'case_name':<28} {'total':>6} {'correct':>8} {'accuracy':>10}"
    print(header)
    print("-" * len(header))
    for r in rows:
        if r.get("status") != "ok":
            print(f"{r['case_name']:<28} {r.get('status', '?'):>6}")
            continue
        print(
            f"{r['case_name']:<28} "
            f"{r['total_fields']:>6} "
            f"{r['correct_fields']:>8} "
            f"{r['accuracy']*100:>9.2f}%"
        )


def print_mismatches(rows: List[Dict[str, Any]]) -> None:
    for r in rows:
        if r.get("status") != "ok":
            continue
        if not r["mismatches"]:
            print(f"\n[{r['case_name']}] no mismatches")
            continue
        print(f"\n[{r['case_name']}] mismatches:")
        for m in r["mismatches"]:
            print(
                f"  - {m['field']}\n"
                f"      expected: {m['expected']!r}\n"
                f"      actual:   {m['actual']!r}"
            )


# -------------------------
# Main
# -------------------------
def main() -> None:
    rows = [evaluate_case(c) for c in CASES]
    print_summary(rows)
    print_mismatches(rows)

    aggregate: Dict[str, Any] = {
        "cases": rows,
    }
    ok_rows = [r for r in rows if r.get("status") == "ok"]
    if ok_rows:
        total = sum(r["total_fields"] for r in ok_rows)
        correct = sum(r["correct_fields"] for r in ok_rows)
        aggregate["overall"] = {
            "total_fields": total,
            "correct_fields": correct,
            "accuracy": round(correct / total, 4) if total else 0.0,
        }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "salesforce_evaluation.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(aggregate, f, indent=2, ensure_ascii=False)
    print(f"\nsaved -> {out_path}")


if __name__ == "__main__":
    main()
