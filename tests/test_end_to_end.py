import json
import types

import pytest
from fastapi.testclient import TestClient

from parser import parse_file
from main import app


def make_response(text: str):
    # simple object with .text attribute
    obj = types.SimpleNamespace()
    obj.text = text
    return obj


def test_parse_json_and_map(monkeypatch):
    # sample input JSON (list of one record)
    sample = [{"FirstName": "Jane", "LastName": "Doe", "BusinessPartner": "BP001"}]
    content = json.dumps(sample).encode()

    parsed = parse_file("sample.json", content)
    assert isinstance(parsed, list)
    assert parsed[0]["FirstName"] == "Jane"

    # now import ai_mapper and monkeypatch its model.generate_content
    import ai_mapper

    # Prepare a fake mapping output that matches the BusinessPartner schema
    mapped = {"BusinessPartner": "BP001", "FirstName": "Jane", "LastName": "Doe"}
    fake_text = json.dumps(mapped)

    monkeypatch.setattr(ai_mapper.model, "generate_content", lambda prompt: make_response(fake_text))

    result = ai_mapper.map_to_sap(parsed, "BusinessPartner")
    # result should be a list with mapped dict
    assert isinstance(result, list)
    assert result[0]["BusinessPartner"] == "BP001"
    assert result[0]["FirstName"] == "Jane"


def test_semantic_field_mapping(monkeypatch):
    """Test that AI mapping can semantically map different wording to target schema."""
    # source uses different field names
    sample = [{"given_name": "Alice", "surname": "Wong", "email_address": "alice@example.com"}]
    content = json.dumps(sample).encode()

    parsed = parse_file("sample.json", content)

    import ai_mapper

    # fake generate_content that reads the prompt, extracts SOURCE DATA and returns a semantically mapped JSON
    def fake_generate(prompt):
        # simple heuristic: find the SOURCE DATA JSON block in the prompt
        import re
        m = re.search(r"SOURCE DATA:\n(\{.*\}|\[.*\])", prompt, flags=re.S)
        if not m:
            return make_response(json.dumps({}))
        src_text = m.group(1)
        src = json.loads(src_text)
        # src might be dict or list
        if isinstance(src, list):
            src = src[0]

        mapped = {
            "BusinessPartner": "AUTO_BP",
            "FirstName": src.get("given_name") or src.get("first_name") or src.get("fname"),
            "LastName": src.get("surname") or src.get("last_name") or src.get("lname"),
            "to_EmailAddress": [{"EmailAddress": src.get("email_address") or src.get("email")}]
        }
        return make_response(json.dumps(mapped))

    monkeypatch.setattr(ai_mapper.model, "generate_content", lambda prompt: fake_generate(prompt))

    result = ai_mapper.map_to_sap(parsed, "BusinessPartner")
    assert isinstance(result, list)
    out = result[0]
    assert out["FirstName"] == "Alice"
    assert out["LastName"] == "Wong"
    assert out["to_EmailAddress"][0]["EmailAddress"] == "alice@example.com"


def test_upload_returns_mapped_json_for_cap(monkeypatch):
    client = TestClient(app)

    import ai_mapper

    mapped = {"BusinessPartner": "BP002", "FirstName": "Bob", "LastName": "Lee"}
    monkeypatch.setattr(ai_mapper.model, "generate_content", lambda prompt: make_response(json.dumps(mapped)))

    source = [{"FirstName": "Bob", "LastName": "Lee", "BusinessPartner": "BP002"}]
    files = {
        "file": ("sample.json", json.dumps(source), "application/json")
    }

    response = client.post("/upload", files=files, data={"target_schema": "BusinessPartner"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["file_name"] == "sample.json"
    assert payload["target_schema"] == "BusinessPartner"
    assert isinstance(payload["mapped_result"], list)
    assert payload["mapped_result"][0]["BusinessPartner"] == "BP002"
