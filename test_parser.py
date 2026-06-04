from parser import parse_file

# -------------------------
# Test CSV
# -------------------------
print("=== CSV TEST ===")

with open("CRM_input.csv", "rb") as f:
    csv_result = parse_file("CRM_input.csv", f.read())

print(csv_result)


# -------------------------
# Test JSON
# -------------------------
print("=== JSON TEST ===")

with open("CRM_input.json", "rb") as f:
    json_result = parse_file("CRM_input.json", f.read())

print(json_result)