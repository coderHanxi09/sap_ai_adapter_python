# Legacy Salesforce → BusinessPartner scenario (archived)

These are the **old** Salesforce test artifacts that mapped Salesforce
Account/Contact CSV exports to the SAP **BusinessPartner** schema.

This design was superseded: the real Salesforce → SAP target is the
**JournalEntryCreateRequest** (invoice → accounting document) scenario, which
lives in the active project (`test_salesforce_invoice.py`,
`schemas.JournalEntryRequestModel`, `test_data/salesforce/salesforce_input_invoice.json`).

Everything here is kept for reference only and is **not needed for now**.

## Contents

- `test_data/` — the 8 input CSV cases (`sf_*.csv`)
- `expected_outputs/` — expected BusinessPartner JSON for each case
- `actual_outputs/` — last recorded actual outputs
- `actual_outputs/stability/` — 8-run stability outputs for `sf_account_renamed`
- `evaluation_results/` — field-level accuracy + stability reports
- `scripts/` — the old runner/eval scripts:
  - `test_salesforce_mapper.py`
  - `evaluate_salesforce.py`
  - `stability_salesforce.py`

## How to restore

These scripts expect to run from the project root and reference paths like
`test_data/salesforce/` and `actual_outputs/salesforce/`. To reactivate:

1. Move the CSVs back to `test_data/salesforce/`.
2. Move the scripts back to the project root.
3. Move expected/actual/evaluation files back to their original folders.

Note: they map with `target_schema="BusinessPartner"`, not the new
`JournalEntry` schema.
