"""
End-to-end test for the Salesforce source-system scenario.

Reads CSV files from test_data/salesforce/, runs them through the parser
and Gemini-backed mapper with source_system="salesforce", prints the
resulting BusinessPartner JSON, and stores each result under
actual_outputs/salesforce/<case_name>_actual.json so that
evaluate_salesforce.py can score them later.
"""

import argparse
import json
import sys
import time
from pathlib import Path

from parser import parse_file
from ai_mapper import map_to_sap


BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "test_data" / "salesforce"
OUTPUT_DIR = BASE_DIR / "actual_outputs" / "salesforce"

CASES = [
    "sf_account_standard.csv",
    "sf_contact_standard.csv",
    "sf_account_renamed.csv",
    "sf_account_uk_customer.csv",
    "sf_account_china_standard.csv",
    "sf_contact_japan.csv",
    "sf_account_partner.csv",
    "sf_account_sparse_renamed.csv",
]

MAX_ATTEMPTS = 4
BACKOFF_SECONDS = [5, 15, 30]


def map_with_retry(parsed, label: str):
    """Call map_to_sap with a small backoff loop to survive transient 5xx."""
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


def run_case(filename: str, force: bool) -> None:
    case_name = Path(filename).stem
    input_path = INPUT_DIR / filename
    out_path = OUTPUT_DIR / f"{case_name}_actual.json"

    print(f"\n=== Salesforce case: {case_name} ===", flush=True)
    print(f"input:  {input_path}", flush=True)
    print(f"output: {out_path}", flush=True)

    if out_path.exists() and not force:
        print("already exists, skipping (use --force to overwrite)", flush=True)
        return

    with open(input_path, "rb") as f:
        parsed = parse_file(filename, f.read())

    result = map_with_retry(parsed, label=case_name)

    print(json.dumps(result, indent=2, ensure_ascii=False), flush=True)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"saved -> {out_path}", flush=True)


def main() -> None:
    parser_ = argparse.ArgumentParser()
    parser_.add_argument(
        "--force",
        action="store_true",
        help="re-run cases even if their *_actual.json file already exists",
    )
    parser_.add_argument(
        "--only",
        nargs="*",
        default=None,
        help="run only the named cases (filenames without extension)",
    )
    args = parser_.parse_args()

    selected = CASES
    if args.only:
        wanted = set(args.only)
        selected = [c for c in CASES if Path(c).stem in wanted]

    for filename in selected:
        run_case(filename, force=args.force)


if __name__ == "__main__":
    main()
