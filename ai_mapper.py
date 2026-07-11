import os
import json
import re
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from schemas import BusinessPartnerRequestModel, JournalEntryRequestModel

# -------------------------
# Load env
# -------------------------
load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

# -------------------------
# Schema registry
# -------------------------
SCHEMA_REGISTRY = {
    "BusinessPartner": BusinessPartnerRequestModel,
    "JournalEntry": JournalEntryRequestModel,
}

# -------------------------
# Salesforce Invoice -> SAP Journal Entry instructions
# -------------------------
def build_salesforce_invoice_instructions() -> str:
    return """
SOURCE SYSTEM: SALESFORCE (Invoice document)
TARGET: SAP S/4HANA JournalEntryCreateRequest (accounting document)

You receive a Salesforce Invoice object with root key "Invoice".
Produce ONLY a valid JSON object matching the SAP JournalEntryCreateRequest target schema.
Do not include markdown, explanations, comments, or any text outside JSON.

OUTPUT SHAPE RULES:
- The output must always be a single JSON object.
- Do not return an array under any circumstance.
- The root object must directly contain "MessageHeader" and "JournalEntryCreateRequest".

This mapping is for the Salesforce invoice posting scenario. Therefore, SAP posting
defaults that are fixed for this integration scenario are allowed and required.
Do not leave a field null when a deterministic rule below is defined.

HEADER / MESSAGE HEADER RULES:
- Top-level MessageHeader.ID = "SF-" + Invoice.Id.
- JournalEntryCreateRequest.MessageHeader.ID = "SF-" + Invoice.Id.
- Top-level MessageHeader.CreationDateTime:
  - Use Invoice.CreatedDate or Invoice.CreatedDateTime if present.
  - Otherwise use Invoice.InvoiceDate + "T10:00:00Z".

JOURNAL ENTRY HEADER MAPPING:
- OriginalReferenceDocumentType = "BKPFF".
- OriginalReferenceDocument = Invoice.Id.
- BusinessTransactionType = "RFBU".
- AccountingDocumentType = "DR".
- CompanyCode = Invoice.CompanyCode.
- DocumentDate = Invoice.InvoiceDate.
- PostingDate = Invoice.InvoiceDate.
- AccountingDocumentHeaderText = "SF Invoice " + Invoice.Id.
- CreatedByUser = "IF_SALESFORCE".
- TransactionCurrency = Invoice.CurrencyIsoCode.
- Reference1InDocumentHeader = Invoice.AccountId.
- Reference2InDocumentHeader = Invoice.AccountExternalNumber.
- DocumentReferenceID = "SF-" + Invoice.Id.

ITEM / LINE MAPPING:
Build a balanced double-entry posting. The total debit amount must equal the total
credit amount. For a standard Salesforce customer invoice, create the following lines.

1. RECEIVABLE LINE, debit:
- ReferenceDocumentItem = "1".
- GLAccount = "140000".
- AmountInTransactionCurrency = Invoice.TotalAmount formatted as a string with two decimals.
- DebitCreditCode = "S".
- Customer = Invoice.AccountExternalNumber.
- AssignmentReference = Invoice.Id.
- DocumentItemText = "Receivable SF Invoice".
- ProfitCenter = Invoice.BusinessUnit if present, otherwise use the first line item's ProfitCenter.
- TaxCode = "".

2. REVENUE LINES, credit:
For each entry in Invoice.InvoiceLineItems, create one revenue line.
- ReferenceDocumentItem = sequential number as string, starting from "2".
- GLAccount = lineItem.RevenueGLCode.
- AmountInTransactionCurrency = lineItem.LineAmount formatted as a string with two decimals.
- DebitCreditCode = "H".
- Customer = "".
- AssignmentReference = Invoice.Id.
- DocumentItemText = lineItem.Description.
- ProfitCenter = lineItem.ProfitCenter.
- TaxCode = lineItem.TaxCode.

3. TAX LINE, credit:
If Invoice.TotalTaxAmount > 0, create one tax line after all revenue lines.
- ReferenceDocumentItem = next sequential item number as string.
- GLAccount = "177600".
- AmountInTransactionCurrency = Invoice.TotalTaxAmount formatted as a string with two decimals.
- DebitCreditCode = "H".
- Customer = "".
- AssignmentReference = Invoice.Id.
- DocumentItemText:
  - If the source input provides an explicit tax rate, set DocumentItemText to "VAT {rate}%".
  - If no explicit tax rate is provided, set DocumentItemText to "VAT".
  - Do not infer a 19% VAT rate only from TaxCode = "A1".
- ProfitCenter = Invoice.BusinessUnit if present, otherwise use the first line item's ProfitCenter.
- TaxCode should be copied from the related invoice line item when available.

AMOUNT FORMATTING:
- Output all amounts as strings with exactly two decimals.
- Example: 1000.0 -> "1000.00"; 1190 -> "1190.00".

NULL / EMPTY VALUE RULES:
- Do not use null for fields with deterministic rules in this prompt.
- For empty Customer fields on revenue and tax lines, use "".
- For empty TaxCode on the receivable line, use "".
- Use null only for optional target fields where no rule and no source value exist.
- Do not invent values outside the rules above.

EXPECTED STRUCTURE:
{
  "MessageHeader": {
    "ID": "SF-<Invoice.Id>",
    "CreationDateTime": "<timestamp>"
  },
  "JournalEntryCreateRequest": {
    "MessageHeader": {
      "ID": "SF-<Invoice.Id>"
    },
    "JournalEntry": {
      "OriginalReferenceDocumentType": "BKPFF",
      "OriginalReferenceDocument": "<Invoice.Id>",
      "BusinessTransactionType": "RFBU",
      "AccountingDocumentType": "DR",
      "CompanyCode": "<Invoice.CompanyCode>",
      "DocumentDate": "<Invoice.InvoiceDate>",
      "PostingDate": "<Invoice.InvoiceDate>",
      "AccountingDocumentHeaderText": "SF Invoice <Invoice.Id>",
      "CreatedByUser": "IF_SALESFORCE",
      "TransactionCurrency": "<Invoice.CurrencyIsoCode>",
      "Reference1InDocumentHeader": "<Invoice.AccountId>",
      "Reference2InDocumentHeader": "<Invoice.AccountExternalNumber>",
      "DocumentReferenceID": "SF-<Invoice.Id>",
      "Item": [
        {
          "ReferenceDocumentItem": "1",
          "GLAccount": "140000",
          "AmountInTransactionCurrency": "<Invoice.TotalAmount>",
          "DebitCreditCode": "S",
          "Customer": "<Invoice.AccountExternalNumber>",
          "AssignmentReference": "<Invoice.Id>",
          "DocumentItemText": "Receivable SF Invoice",
          "ProfitCenter": "<ProfitCenter>",
          "TaxCode": ""
        },
        {
          "ReferenceDocumentItem": "2",
          "GLAccount": "<lineItem.RevenueGLCode>",
          "AmountInTransactionCurrency": "<lineItem.LineAmount>",
          "DebitCreditCode": "H",
          "Customer": "",
          "AssignmentReference": "<Invoice.Id>",
          "DocumentItemText": "<lineItem.Description>",
          "ProfitCenter": "<lineItem.ProfitCenter>",
          "TaxCode": "<lineItem.TaxCode>"
        },
        {
          "ReferenceDocumentItem": "3",
          "GLAccount": "177600",
          "AmountInTransactionCurrency": "<Invoice.TotalTaxAmount>",
          "DebitCreditCode": "H",
          "Customer": "",
          "AssignmentReference": "<Invoice.Id>",
          "DocumentItemText": "VAT",
          "ProfitCenter": "<ProfitCenter>",
          "TaxCode": "<TaxCode>"
        }
      ]
    }
  }
}
"""


# -------------------------
# Source-system specific instructions
# -------------------------
def build_source_instructions(source_system: str, target_schema: str = "BusinessPartner") -> str:
    """
    Return extra mapping guidance based on the source system of the input data
    and the target schema being produced.

    Supported values:
    - source_system "salesforce" + target "JournalEntry": Salesforce Invoice ->
      SAP JournalEntryCreateRequest
    - source_system "salesforce" + target "BusinessPartner": Salesforce
      Account / Contact CSV exports
    - "crm" / "generic" / anything else: no extra instructions (current behavior)
    """
    system = (source_system or "generic").strip().lower()
    schema = (target_schema or "BusinessPartner").strip()

    if system == "salesforce" and schema == "JournalEntry":
        return build_salesforce_invoice_instructions()

    if system == "salesforce":
        return """
SOURCE SYSTEM: SALESFORCE
The input is exported from Salesforce (Account or Contact object,
either with standard Salesforce field names or with renamed columns).

SALESFORCE -> SAP BUSINESS PARTNER MAPPING RULES:

Object type detection:
- If the record looks like a Salesforce Account (has Name / company_name /
  Account Name / AccountNumber / Industry / BillingStreet etc.):
    -> map to a Business Partner with BusinessPartnerCategory = "2"
       (organization), if the schema supports BusinessPartnerCategory.
- If the record looks like a Salesforce Contact (has FirstName + LastName +
  Email / MailingStreet etc.):
    -> map to a Business Partner with BusinessPartnerCategory = "1"
       (person), if the schema supports BusinessPartnerCategory.

Field mapping (only map when the target field exists in the schema):
- Account Name / Name / company_name        -> OrganizationBPName1
- FirstName                                  -> ContactPerson.FirstName
- LastName                                   -> ContactPerson.LastName
- Email / email                              -> ContactPerson.EmailAddress
                                                AND/OR address.to_EmailAddress[].EmailAddress
- Phone / tel                                -> ContactPerson.PhoneNumber
                                                AND/OR address.to_PhoneNumber[].PhoneNumber
- BillingStreet / MailingStreet / invoice_address -> StreetName
  (you may split a trailing house number into HouseNumber if clearly present)
- BillingCity / MailingCity / city           -> CityName
- BillingPostalCode / MailingPostalCode / zip -> PostalCode
- BillingCountry / MailingCountry / nation   -> Country (normalized, see below)
- Website / homepage                         -> WebsiteURL
- Industry / business_area                   -> Industry
- AccountNumber / client_no                  -> ExternalReference.SourceCustomerID
                                                (also acceptable: SearchTerm1 if no
                                                 ExternalReference field exists)
- Salesforce Id / sf_id                      -> ExternalReference.SourceSystem = "SALESFORCE"
                                                and the Id can be ignored if it does not
                                                fit any schema field
- Type = "Customer"                          -> add to_BusinessPartnerRole entry with
                                                BusinessPartnerRole = "FLCU01"
                                                (only if the schema supports it)

Country normalization (always apply when mapping to Country):
- "United States" / "USA" / "U.S." / "US"          -> "US"
- "Germany" / "Deutschland" / "DE"                 -> "DE"
- "China" / "PRC" / "CN"                           -> "CN"
- "UK" / "United Kingdom" / "Great Britain" / "GB" -> "GB"
- Already valid ISO-2 codes stay as-is.

ALLOWED INFERENCES (do not treat as hallucination):
- Setting BusinessPartnerCategory based on Account vs Contact.
- Setting BusinessPartnerRole = "FLCU01" when Type = "Customer"
  and the schema supports BusinessPartnerRole.
- Setting ExternalReference.SourceSystem = "SALESFORCE".
- Country normalization to ISO 2-letter codes.


NOT ALLOWED:
- Do NOT invent tax numbers, languages, grouping codes or any other SAP
  customizing values that are not present in the source.
- Do NOT add fields that are not defined by the target schema.
- For Salesforce data, ExternalReference.SourceSystem must be "SALESFORCE"
  (not "CRM"); CRM-specific role/grouping defaults in the detailed rules above
  do not apply unless the input is clearly CRM-shaped.
""".strip()

    return ""


# -------------------------
# Core Business Partner mapping rules
# -------------------------
def build_mapping_rules(target_schema: str = "BusinessPartner") -> str:
    """
    Deterministic mapping rules shared by all source systems.
    Source-specific blocks (e.g. Salesforce) may add overrides below these.

    These detailed rules are Business Partner specific. For other target schemas
    (e.g. JournalEntry) the schema-specific guidance comes from
    build_source_instructions() instead, so return an empty block here.
    """
    if (target_schema or "BusinessPartner").strip() != "BusinessPartner":
        return ""

    return """
DETAILED MAPPING RULES:

1. General output rules
- Return valid JSON only.
- Do not include Markdown, comments, explanations or code fences.
- Map only to fields supported by the provided target schema.
- Preserve original input values unless a deterministic rule below says otherwise.
- For missing scalar fields, use null.
- For missing collection fields, use [].
- Do not invent SAP-specific code values.
- Do not invent fields that are not supported by the schema.

2. Business Partner Category rules
- If the input represents a company, organization, GmbH, Ltd, Inc, Corp,
  Corporation, AG, KG, LLC or similar legal entity, set
  BusinessPartnerCategory to "2".
- If the input clearly represents an individual person only, set
  BusinessPartnerCategory to "1".
- Do not classify a company such as "Alpine Sports Retail GmbH" as a person.

3. SearchTerm1 rules
- Derive SearchTerm1 from the company name.
- Remove legal suffixes such as GmbH, Ltd, Inc, Corp, Corporation, AG, KG, LLC.
- For "Alpine Sports Retail GmbH", SearchTerm1 must be "Alpine Sports Retail".
- Do not shorten it further to "Alpine" or "Alpine Sports" unless a schema
  length limit requires it.

4. Language and CorrespondenceLanguage rules
- If the input does not explicitly provide Language, set Language to "EN".
- If the input does not explicitly provide CorrespondenceLanguage, set
  CorrespondenceLanguage to "EN".
- Do not infer Language or CorrespondenceLanguage from Country.
- For example, Country = "DE" does not mean Language must be "DE".

5. BusinessPartnerGrouping rules
- If the source data appears to come from CRM or contains customer/account data,
  set BusinessPartnerGrouping to "ZCRM" if the schema supports this field.
- Do not leave BusinessPartnerGrouping null for CRM customer/account data.

6. BusinessPartnerRole rules
- For CRM customer/account data, BusinessPartnerRole should include:
  - BUP001
  - FLCU00
  - FLCU01
- Do not invent additional roles.
- Do not add FSCU00 unless it is explicitly present in the input.
- Do not add supplier, employee or financial service roles unless explicitly
  present in the input.

7. Tax rules
- If taxId or tax number starts with "DE", set BPTaxType to "DE0".
- Preserve BPTaxNumber exactly as provided.
- For example, "DE123456789" must remain "DE123456789".
- Do not remove the "DE" prefix.
- Do not replace DE0 with DE1, DE, MWS1 or any other tax type unless explicitly
  provided in the input.

8. Address rules
- If a street string clearly contains a house number, extract the house number
  into HouseNumber.
- Example: "Hauptstraße 12" -> HouseNumber = "12".
- Keep address values unchanged otherwise.
- Do not translate street names, city names or country names.
- Normalize countries only when deterministic:
  - Germany -> DE
  - Deutschland -> DE
  - United States -> US
  - USA -> US
  - China -> CN
  - UK -> GB
  - United Kingdom -> GB

9. ExternalReference rules
- If the source is CRM/customer/account data, set ExternalReference.SourceSystem
  to "CRM" if the schema supports this field.
- Map customerId, customer_id, accountId, account_id, AccountNumber or similar
  customer identifiers to ExternalReference.SourceCustomerID if supported.
- Do not invent SourceSystem values such as SOURCE, CRM_SOURCE, SOURCE_CRM or
  EXTERNAL_CRM.

10. Contact and website rules
- Map website or web address to WebsiteURL if supported.
- Map primary contact first name, last name, email and phone to the contact
  person structure if supported.
- Preserve names, emails and phone numbers exactly as provided.
- Do not translate company names, person names, addresses, emails or websites.

11. Forbidden inference rules
- Do not create values that are not present in the input and not defined by the
  rules above.
- Do not invent SAP roles, tax categories or source system labels.
- Do not change an organization into a person if the input contains a company name.
- Do not remove prefixes from tax numbers.
- Do not translate company names, person names, addresses, emails or websites.

REFERENCE TARGET (Alpine Sports Retail GmbH CRM case):
- BusinessPartnerCategory = "2"
- SearchTerm1 = "Alpine Sports Retail"
- Language = "EN"
- CorrespondenceLanguage = "EN"
- BusinessPartnerGrouping = "ZCRM"
- BusinessPartnerRole includes BUP001, FLCU00 and FLCU01
- BPTaxType = "DE0"
- BPTaxNumber = "DE123456789"
- ExternalReference.SourceSystem = "CRM"
- ExternalReference.SourceCustomerID = "ACC-100234"
""".strip()


# -------------------------
# Prompt builder (SAFE)
# -------------------------
def build_prompt(source: dict, schema_class, source_system: str = "generic", target_schema: str = "BusinessPartner"):
    schema_json = json.dumps(schema_class.model_json_schema(), indent=2)
    source_json = json.dumps(source, indent=2, ensure_ascii=False)
    source_instructions = build_source_instructions(source_system, target_schema)

    source_block = (
        f"\n\n{source_instructions}\n"
        if source_instructions
        else ""
    )
    mapping_rules = build_mapping_rules(target_schema)

    prompt_template = """
You are an SAP S/4HANA data mapping engine.

TASK:
Transform input business data into SAP S/4HANA-compatible OData JSON payloads.

STRICT OUTPUT RULES:
- Output ONLY raw valid JSON
- Do NOT use markdown
- Do NOT wrap output in code fences
- Do NOT include explanations or comments
- Must be JSON.parse() compatible
- Response must start with {{
- Response must end with }}

JSON RULES:
- For missing scalar fields, use null
- For missing collection fields, use []
- Do not output undefined
- Map only to fields supported by the target schema

SAP S/4HANA RULES:
- Follow schema exactly
- Do not invent SAP customizing values
- Navigation properties must always be arrays

{mapping_rules}
{source_block}
TARGET SCHEMA:
{schema}

SOURCE:
{source}

Return ONLY JSON.
"""

    return prompt_template.format(
        schema=schema_json,
        source=source_json,
        mapping_rules=mapping_rules,
        source_block=source_block
    ).strip()

# -------------------------
# Robust JSON extractor
# -------------------------
def extract_json(text: str):
    """
    Extract first valid JSON object from LLM output safely
    """
    text = text.strip()

    # remove markdown fences
    text = re.sub(r"```(?:json)?", "", text)
    text = text.replace("```", "").strip()

    # find first JSON object
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError("No JSON object found")

    json_str = match.group(0)
    return json.loads(json_str)

# -------------------------
# Main mapping engine
# -------------------------
def map_to_sap(source, target_schema: str, source_system: str = "generic"):

    schema_class = SCHEMA_REGISTRY[target_schema]

    def _map_single(item):

        prompt = build_prompt(item, schema_class, source_system=source_system, target_schema=target_schema)

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        text = response.text

        try:
            result = extract_json(text)

            validated = schema_class.model_validate(result)

            return validated.model_dump()

        except Exception as e:
            return {
                "error": "Invalid output",
                "exception": str(e),
                "raw_output": text
            }

    # JournalEntry represents a single accounting document (JournalEntryCreateRequest).
    # A Salesforce invoice input (whether nested JSON or a single-row flattened CSV,
    # which the parser wraps in a list) must always map to ONE JSON object, never an
    # array. Only fall back to a list when there are genuinely multiple invoice rows.
    if target_schema == "JournalEntry":
        if isinstance(source, list):
            if len(source) == 1:
                return _map_single(source[0])
            return [_map_single(i) for i in source]
        return _map_single(source)

    if isinstance(source, list):
        return [_map_single(i) for i in source]

    return _map_single(source)