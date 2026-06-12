# Salesforce scenario

## Purpose

The SAP AI Adapter is designed to ingest CRM-style records from many
source systems and emit SAP S/4HANA Business Partner-compatible JSON.
The Salesforce scenario validates that the adapter is genuinely generic:
it must process Salesforce Account / Contact exports — both with the
official Salesforce field names and with renamed columns — without any
schema change and without breaking the existing CRM/professor flow.

It exercises three things:

1. **Field mapping coverage** — Salesforce-specific fields land in the
   right SAP fields.
2. **Inference correctness** — the adapter applies sensible defaults
   (e.g. `BusinessPartnerCategory`, country normalization,
   `BusinessPartnerRole = FLCU01`) without hallucinating SAP customizing
   values.
3. **Stability** — the same input produces a stable, schema-valid output
   across multiple Gemini runs.

## Input files

All inputs live under `test_data/salesforce/`.

| File | Shape | Notes |
| --- | --- | --- |
| `sf_account_standard.csv` | Salesforce Account export | `Id`, `AccountNumber`, `Name`, `Type=Customer`, `Industry`, `Phone`, `Website`, `BillingStreet/City/PostalCode/Country` |
| `sf_contact_standard.csv` | Salesforce Contact export | `Id`, `AccountId`, `FirstName`, `LastName`, `Email`, `Phone`, `MailingStreet/City/PostalCode/Country` |
| `sf_account_renamed.csv` | Account export with renamed columns | `sf_id`, `client_no`, `company_name`, `business_area`, `tel`, `homepage`, `invoice_address`, `city`, `zip`, `nation` |
| `sf_account_uk_customer.csv` | UK Customer Account | `United Kingdom` → `GB`, `Type=Customer` → `FLCU01` |
| `sf_account_china_standard.csv` | China Customer Account | `China` → `CN`, standard Salesforce billing columns |
| `sf_contact_japan.csv` | Japan Contact | `BusinessPartnerCategory=1`, Japanese address and contact fields |
| `sf_account_partner.csv` | Partner Account (non-customer) | `Type=Partner` — should **not** infer `FLCU01` role |
| `sf_account_sparse_renamed.csv` | Minimal renamed Account | Only `company_name`, address, `client_no`; no phone/website/industry |

## API usage

The `/upload` endpoint stays backward-compatible. To opt into the
Salesforce-aware prompt, pass `source_system=salesforce`.

```
POST /upload?target_schema=BusinessPartner&source_system=salesforce&mode=raw
```

`source_system` accepts:

- `generic` (default) — original behavior.
- `crm` — same as generic, kept for clarity in callers.
- `salesforce` — adds Salesforce-specific mapping rules to the prompt.

`mode` is unchanged:

- `cap` (default) — `{ "value": <result> }`, safe for SAP CAP / OData.
- `raw` — verbose envelope including `source_system`, used for
  debugging and evaluation.

### curl example

```bash
curl -X POST \
  "http://localhost:8000/upload?target_schema=BusinessPartner&source_system=salesforce&mode=raw" \
  -F "file=@test_data/salesforce/sf_account_standard.csv"
```

The CAP-style call is identical, just drop `mode=raw`:

```bash
curl -X POST \
  "http://localhost:8000/upload?target_schema=BusinessPartner&source_system=salesforce" \
  -F "file=@test_data/salesforce/sf_account_renamed.csv"
```

## Mapping rules (summary)

The full list lives in `ai_mapper.build_source_instructions("salesforce")`.
Highlights:

- Salesforce **Account** → `BusinessPartnerCategory = "2"`.
- Salesforce **Contact** → `BusinessPartnerCategory = "1"`,
  with `FirstName / LastName / Email / Phone` going into
  `ContactPerson`.
- `Account Name` / `Name` / `company_name` → `OrganizationBPName1`.
- `BillingStreet` / `MailingStreet` / `invoice_address` → `StreetName`
  (a trailing house number may be split into `HouseNumber`).
- `BillingCity / MailingCity / city` → `CityName`,
  `BillingPostalCode / MailingPostalCode / zip` → `PostalCode`,
  `BillingCountry / MailingCountry / nation` → `Country`
  (normalized to ISO 2-letter codes).
- `Phone / tel` → `to_PhoneNumber[].PhoneNumber` and/or
  `ContactPerson.PhoneNumber`.
- `Email / email` → `to_EmailAddress[].EmailAddress` and/or
  `ContactPerson.EmailAddress`.
- `AccountNumber / client_no` → `ExternalReference.SourceCustomerID`.
- `Salesforce Id / sf_id` → `ExternalReference.SourceSystem = "SALESFORCE"`.
- `Type = Customer` → adds `to_BusinessPartnerRole[]` with
  `BusinessPartnerRole = "FLCU01"`.

Country normalization:

| Input | Output |
| --- | --- |
| `United States`, `USA` | `US` |
| `Germany`, `Deutschland` | `DE` |
| `China`, `PRC` | `CN` |
| `UK`, `United Kingdom`, `Great Britain` | `GB` |

## Evaluation metrics

Three scripts cover the scenario, all designed to be run from inside
`sap_ai_adapter_python/`.

### 1. `python test_salesforce_mapper.py`

Runs each Salesforce CSV through `parse_file` + `map_to_sap` with
`source_system="salesforce"` and writes:

```
actual_outputs/salesforce/sf_account_standard_actual.json
actual_outputs/salesforce/sf_contact_standard_actual.json
actual_outputs/salesforce/sf_account_renamed_actual.json
```

### 2. `python evaluate_salesforce.py` — field-level accuracy

Compares each `*_actual.json` against the matching
`expected_outputs/salesforce/*_expected.json`:

- Both sides are flattened to dot-paths
  (`BusinessPartner.to_BusinessPartnerAddress[0].Country`, etc.).
- Only fields that are non-null in the expected file are scored
  (other fields are "don't care").
- Strings are compared case-insensitively after trimming.

The summary table reports `case_name, total_fields, correct_fields,
accuracy`, followed by per-field mismatches. The aggregate is saved to
`evaluation_results/salesforce_evaluation.json`.

### 3. `python stability_salesforce.py` — stability across 8 runs

Runs `sf_account_renamed.csv` through the mapper 8 times, saves each
result to `actual_outputs/salesforce/stability/run_<N>.json`, and
reports:

- `unique_outputs` and `fully_identical`: whether the canonical
  serialization is byte-for-byte stable.
- `row_field_diffs`: which top-level `BusinessPartner.*` fields are
  always present and which are sometimes missing across runs.

The aggregate is saved to
`evaluation_results/salesforce_stability.json`.

### Unsupported-inference / hallucination analysis

The mismatch list from `evaluate_salesforce.py` doubles as a
hallucination probe:

- Fields where `actual` has a value but `expected` does not are
  candidate hallucinations (the LLM invented an SAP customizing value).
- Fields where `expected` has a value but `actual` is missing are
  *under*-inference (mapping rules were not applied).
- The stability report shows whether such gaps are random
  (LLM jitter) or consistent (prompt issue).

## Why this scenario matters

The original CRM/professor tests proved the adapter could turn one
fixed input shape into a Business Partner. The Salesforce scenario
proves the same adapter — same `/upload` endpoint, same Pydantic
schema, same Gemini model — can absorb a *different* CRM source
system, including renamed columns, without code changes downstream.
That is the actual definition of "generic" for this service.
