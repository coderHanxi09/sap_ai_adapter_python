from parser import parse_file
from ai_mapper import map_to_sap

# -------------------------
# CSV → LLM test
# -------------------------
print("=== CSV → LLM ===")

with open("CRM_input.csv", "rb") as f:
    csv_data = parse_file("CRM_input.csv", f.read())

result_csv = map_to_sap(csv_data, "BusinessPartner")
print(result_csv)


# -------------------------
# JSON → LLM test
# -------------------------
print("=== JSON → LLM ===")

with open("CRM_input.json", "rb") as f:
    json_data = parse_file("CRM_input.json", f.read())

result_json = map_to_sap(json_data, "BusinessPartner")
print(result_json)