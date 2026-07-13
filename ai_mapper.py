import os
import json
import re
import time
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from schemas import BusinessPartnerRequestModel, JournalEntryRequestModel

# -------------------------
# Load env
# -------------------------
load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

# Free-tier models, tried in order. Override with comma-separated GEMINI_MODELS in .env.
DEFAULT_FREE_MODELS = [
    "gemini-3.1-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-3.5-flash",
    "gemini-flash-latest",
]


def _parse_model_list() -> list[str]:
    raw = os.getenv("GEMINI_MODELS", "").strip()
    if raw:
        return [m.strip() for m in raw.split(",") if m.strip()]
    pinned = os.getenv("GEMINI_MODEL", "").strip()
    if pinned:
        return [pinned] + [m for m in DEFAULT_FREE_MODELS if m != pinned]
    return DEFAULT_FREE_MODELS.copy()


FREE_MODEL_CANDIDATES = _parse_model_list()
_last_working_model: str | None = None

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)


def _is_retryable_api_error(exc: Exception) -> bool:
    msg = str(exc)
    return any(code in msg for code in ("429", "404", "503", "UNAVAILABLE", "RESOURCE_EXHAUSTED"))


def _generate_content_with_free_models(prompt: str) -> str:
    """Try free-tier Gemini models in order until one succeeds."""
    global _last_working_model

    models: list[str] = []
    if _last_working_model:
        models.append(_last_working_model)
    for model in FREE_MODEL_CANDIDATES:
        if model not in models:
            models.append(model)

    last_exc: Exception | None = None
    for idx, model in enumerate(models):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
            )
            text = response.text
            if not text:
                raise ValueError(f"Empty response from model {model}")
            if model != _last_working_model:
                print(f"[ai_mapper] using model: {model}", flush=True)
            _last_working_model = model
            return text
        except Exception as exc:
            last_exc = exc
            if idx < len(models) - 1 and _is_retryable_api_error(exc):
                print(
                    f"[ai_mapper] model {model} failed ({type(exc).__name__}); "
                    f"trying next free model...",
                    flush=True,
                )
                if "503" in str(exc):
                    time.sleep(2)
                continue
            break

    raise last_exc  # type: ignore[misc]

# -------------------------
# Schema registry
# -------------------------
SCHEMA_REGISTRY = {
    "BusinessPartner": BusinessPartnerRequestModel,
    "JournalEntry": JournalEntryRequestModel,
}

# -------------------------
# Prompt builder (SAFE)
# -------------------------
# VERSION 1 (archived — original first-edition prompt):
# """
# You are an SAP S/4HANA data mapping engine.
#
# TASK:
# Transform input business data into SAP S/4HANA-compatible OData JSON payloads.
#
# STRICT OUTPUT RULES:
# - Output ONLY raw valid JSON
# - Do NOT use markdown
# - Do NOT wrap output in code fences
# - Do NOT include explanations or comments
# - Must be JSON.parse() compatible
# - Response must start with {
# - Response must end with }
#
# JSON RULES:
# - Never output null
# - Never output undefined
# - Omit unknown fields
# - Use [] for empty collections
#
# SAP S/4HANA RULES:
# - Follow schema exactly
# - Do not invent SAP customizing values
# - Navigation properties must always be arrays
#
# TARGET SCHEMA:
# {schema}
#
# SOURCE:
# {source}
#
# Return ONLY JSON.
# """

def build_prompt(source: dict, schema_class):
    schema_json = json.dumps(schema_class.model_json_schema(), indent=2)
    source_json = json.dumps(source, indent=2)

    prompt_template = """
You are an SAP S/4HANA data mapping engine.

TASK:
Transform input business data into SAP S/4HANA-compatible OData JSON payloads.

STRICT OUTPUT RULES:
- Output ONLY raw valid JSON.
- Do NOT use markdown.
- Do NOT wrap output in code fences.
- Do NOT include explanations or comments.
- Must be JSON.parse() compatible.

JSON RULES:
- Never output null.
- Never output undefined.
- Omit fields that cannot be mapped with sufficient confidence.
- Use [] for empty collections.

MAPPING PRINCIPLES:
- Treat the source data as the primary source of truth.
- Preserve the semantic meaning of the source data.
- Preserve source values whenever possible.
- Only perform transformations that are necessary to satisfy the target schema.
- Do not introduce information that is not supported by the source, the schema, or generally applicable domain knowledge.
- If multiple mappings are possible, choose the mapping requiring the fewest assumptions.
- Prefer omission over speculative mapping.

SAP S/4HANA RULES:
- Follow the target schema exactly.
- Do not generate fields outside the schema.
- Do not invent organization-specific SAP customizing values.
- Produce deterministic and internally consistent mappings.

TARGET SCHEMA:
{schema}

SOURCE:
{source}

Return ONLY valid JSON.
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
def map_to_sap(source, target_schema: str, source_system: str = "generic"):
    schema_class = SCHEMA_REGISTRY[target_schema]

    def _map_single(item):

        prompt = build_prompt(item, schema_class)

        text = _generate_content_with_free_models(prompt)

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

    # JournalEntry: one invoice -> one JSON object (not an array)
    if target_schema == "JournalEntry":
        if isinstance(source, list):
            if len(source) == 1:
                return _map_single(source[0])
            return [_map_single(i) for i in source]
        return _map_single(source)

    if isinstance(source, list):
        return [_map_single(i) for i in source]

    return _map_single(source)
