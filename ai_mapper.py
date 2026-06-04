import os
import json
import re
from dotenv import load_dotenv
from google import genai
from schemas import BusinessPartnerRequestModel

# -------------------------
# Load env
# -------------------------
load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

# -------------------------
# Schema registry
# -------------------------
SCHEMA_REGISTRY = {
    "BusinessPartner": BusinessPartnerRequestModel
}

# -------------------------
# Prompt builder (SAFE)
# -------------------------
def build_prompt(source: dict, schema_class):
    schema_json = json.dumps(schema_class.model_json_schema(), indent=2)
    source_json = json.dumps(source, indent=2)

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
- Never output null
- Never output undefined
- Omit unknown fields
- Use [] for empty collections

SAP S/4HANA RULES:
- Follow schema exactly
- Do not invent SAP customizing values
- Navigation properties must always be arrays

TARGET SCHEMA:
{schema}

SOURCE:
{source}

Return ONLY JSON.
"""

    return prompt_template.format(
        schema=schema_json,
        source=source_json
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
def map_to_sap(source: dict, target_schema: str):

    schema_class = SCHEMA_REGISTRY[target_schema]

    def _map_single(item):

        prompt = build_prompt(item, schema_class)

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

    if isinstance(source, list):
        return [_map_single(i) for i in source]

    return _map_single(source)