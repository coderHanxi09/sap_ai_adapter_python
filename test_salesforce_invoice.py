"""
End-to-end test for the Salesforce Invoice -> SAP Journal Entry scenario.

Reads a Salesforce Invoice JSON document, runs it through the parser and the
Gemini-backed mapper with target_schema="JournalEntry" and
source_system="salesforce", prints the resulting JournalEntryCreateRequest
JSON, and stores the result under
actual_outputs/salesforce/<case_name>_actual.json.

This scenario uses the NEW Salesforce target schema
(schemas.JournalEntryRequestModel), which mirrors
docs/reference/salesforce_to_sap_structure.json and is completely different
from the legacy CRM BusinessPartner schema.
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
    "salesforce_input_invoice.json",
    "salesforce_input_invoice_2.json",
    "salesforce_input_invoice_2.csv",
    "salesforce_input_invoice_3.json",
    "salesforce_input_invoice_3.csv",
    "salesforce_input_invoice_4.json",
    "salesforce_input_invoice_4.csv",
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
                target_schema="JournalEntry",
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

    print(f"\n=== Salesforce Invoice case: {case_name} ===", flush=True)
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
    args = parser_.parse_args()

    for filename in CASES:
        run_case(filename, force=args.force)


if __name__ == "__main__":
    main()
