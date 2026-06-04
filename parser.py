import json
import io
import pandas as pd
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Union


# =========================
# Utils
# =========================

def clean_value(v):
    """Normalize pandas / raw values to SAP-safe format"""
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass

    if isinstance(v, str):
        v = v.strip()
        return v if v != "" else None

    return v


def clean_records(records: List[Dict]) -> List[Dict]:
    return [
        {k: clean_value(v) for k, v in r.items()}
        for r in records
    ]


def normalize_output(data: Any) -> List[Dict]:
    """
    Ensure all parsers output list[dict]
    (important for LLM pipeline consistency)
    """
    if data is None:
        return []

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        return [data]

    return [{"value": str(data)}]


# =========================
# JSON
# =========================

def parse_json(content: bytes) -> Any:
    return json.loads(content.decode("utf-8-sig"))


# =========================
# CSV / TSV
# =========================

def parse_csv(content: bytes):
    df = pd.read_csv(
        io.StringIO(content.decode("utf-8")),
        na_values=["", " ", "null", "NULL"],
        keep_default_na=True
    )
    records = df.to_dict(orient="records")
    return normalize_output(clean_records(records))


def parse_tsv(content: bytes):
    df = pd.read_csv(
        io.StringIO(content.decode("utf-8")),
        sep="\t",
        na_values=["", " ", "null", "NULL"],
        keep_default_na=True
    )
    records = df.to_dict(orient="records")
    return normalize_output(clean_records(records))


# =========================
# XLSX
# =========================

def parse_xlsx(content: bytes):
    df = pd.read_excel(io.BytesIO(content))
    records = df.to_dict(orient="records")
    return normalize_output(clean_records(records))


# =========================
# XML
# =========================

def xml_to_dict(element: ET.Element) -> Any:
    """
    Convert XML → dict while preserving repeating nodes
    """
    children = list(element)

    # leaf node
    if not children:
        text = (element.text or "").strip()
        return text if text else None

    result = {}

    for child in children:
        child_data = xml_to_dict(child)

        if child.tag in result:
            if not isinstance(result[child.tag], list):
                result[child.tag] = [result[child.tag]]
            result[child.tag].append(child_data)
        else:
            result[child.tag] = child_data

    return result


def parse_xml(content: bytes):
    root = ET.fromstring(content.decode("utf-8-sig"))
    return normalize_output(xml_to_dict(root))


# =========================
# TXT
# =========================

def parse_txt(content: bytes):
    text = content.decode("utf-8").strip()
    return [{"text": text}] if text else []


# =========================
# Registry
# =========================

PARSERS = {
    ".json": parse_json,
    ".csv": parse_csv,
    ".tsv": parse_tsv,
    ".xlsx": parse_xlsx,
    ".xml": parse_xml,
    ".txt": parse_txt,
}


# =========================
# Main entry
# =========================

def parse_file(filename: str, content: bytes):
    filename = filename.lower()

    for extension, parser in PARSERS.items():
        if filename.endswith(extension):
            try:
                return parser(content)
            except Exception as e:
                return {
                    "error": str(e),
                    "filename": filename
                }

    raise ValueError(f"Unsupported file type: {filename}")


# =========================
# Example usage
# =========================

if __name__ == "__main__":
    with open("example.csv", "rb") as f:
        parsed = parse_file("example.csv", f.read())

    print(json.dumps(parsed, indent=2, ensure_ascii=False))