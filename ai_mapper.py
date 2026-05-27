import os
import json
import re
try:
    import google.generativeai as genai
    _HAS_GENAI = True
except Exception:
    genai = None
    _HAS_GENAI = False
from dotenv import load_dotenv
from schemas import BusinessPartner

# Load environment variables
load_dotenv()

# Configure Gemini API key (only if SDK is available)
if _HAS_GENAI:
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    # Initialize model
    model = genai.GenerativeModel("gemini-1.5-flash")
else:
    # Dummy model placeholder to allow imports in environments without the SDK.
    class _DummyModel:
        def generate_content(self, *args, **kwargs):
            raise RuntimeError("google.generativeai SDK not available. Install it or mock 'model.generate_content' in tests.")

    model = _DummyModel()


# Schema registry (NOW using real Pydantic models)
SCHEMA_REGISTRY = {
    "BusinessPartner": BusinessPartner
}


# Build structured prompt
def build_prompt(source: dict, schema_class):

    schema_json = schema_class.model_json_schema()

    return f"""
You are an SAP S/4HANA enterprise data mapping engine.

TASK:
Map source data into the target SAP JSON schema.

RULES:
- Output ONLY valid JSON
- No explanation
- No markdown
- Must match schema exactly
- Do not add extra fields
- Do not remove required fields

TARGET SCHEMA:
{json.dumps(schema_json, indent=2)}

SOURCE DATA:
{json.dumps(source, indent=2)}

Return ONLY JSON.
"""


# Safe JSON parser
def safe_parse(text: str):

    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = text.strip()

    return json.loads(text)


# Main mapping function
def map_to_sap(source: dict, target_schema: str):
    schema_class = SCHEMA_REGISTRY.get(target_schema)

    def _map_single(item: dict):
        prompt = build_prompt(item, schema_class)
        response = model.generate_content(prompt)
        text = response.text
        try:
            result = safe_parse(text)
            validated = schema_class.model_validate(result)
            return validated.model_dump()
        except Exception:
            return {
                "error": "Invalid SAP mapping output",
                "raw_output": text
            }

    # Support lists of records by mapping each element
    if isinstance(source, list):
        return [_map_single(item) for item in source]

    if isinstance(source, dict):
        return _map_single(source)

    # unsupported source type
    raise TypeError("Source must be a dict or list of dicts")