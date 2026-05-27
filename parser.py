import json
import io
import pandas as pd
import xml.etree.ElementTree as ET
from typing import Any


def parse_json(content: bytes) -> Any:
    return json.loads(content.decode("utf-8"))


def parse_csv(content: bytes):
    df = pd.read_csv(io.StringIO(content.decode("utf-8")))
    return df.to_dict(orient="records")


def parse_tsv(content: bytes):
    df = pd.read_csv(io.StringIO(content.decode("utf-8")), sep="\t")
    return df.to_dict(orient="records")


def parse_xlsx(content: bytes):
    df = pd.read_excel(io.BytesIO(content))
    return df.to_dict(orient="records")


def xml_to_dict(element):
    result = {}

    # Add child elements
    for child in element:
        child_data = xml_to_dict(child)

        if child.tag in result:
            # Convert to list if duplicate tags exist
            if not isinstance(result[child.tag], list):
                result[child.tag] = [result[child.tag]]

            result[child.tag].append(child_data)
        else:
            result[child.tag] = child_data

    # Add text if element has no children
    text = (element.text or "").strip()
    if text and not result:
        return text

    return result


def parse_xml(content: bytes):
    root = ET.fromstring(content.decode("utf-8"))
    return {root.tag: xml_to_dict(root)}


def parse_txt(content: bytes):
    return {
        "text": content.decode("utf-8")
    }


PARSERS = {
    ".json": parse_json,
    ".csv": parse_csv,
    ".tsv": parse_tsv,
    ".xlsx": parse_xlsx,
    ".xml": parse_xml,
    ".txt": parse_txt,
}


def parse_file(filename: str, content: bytes):
    filename = filename.lower()

    for extension, parser in PARSERS.items():
        if filename.endswith(extension):
            return parser(content)

    raise ValueError(f"Unsupported file type: {filename}")


# Example usage
if __name__ == "__main__":
    with open("example.csv", "rb") as f:
        parsed = parse_file("example.csv", f.read())

    print(parsed)