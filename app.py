from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from ai_mapper import map_to_sap
from parser import parse_file

app = FastAPI(title="SAP AI Adapter Service")


# -----------------------
# Health Check
# -----------------------
@app.get("/")
def health():
    return {"status": "running"}


# -----------------------
# File Upload Endpoint
# -----------------------
@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    target_schema: str = "BusinessPartner",
    mode: str = Query("cap", description="cap | raw"),
    source_system: str = Query(
        "generic",
        description="generic | crm | salesforce"
    )
):
    """
    mode:
    - cap → return {"value": ...} for SAP CAP/OData
    - raw → return pure JSON (for debugging)

    source_system:
    - generic     → no extra mapping hints (default, backward compatible)
    - crm         → legacy CRM/professor scenario, treated as generic
    - salesforce  → enables Salesforce Account/Contact specific prompt
    """

    try:
        # -----------------------
        # File size safety check (10MB limit)
        # -----------------------
        content = await file.read()

        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="File too large")

        # -----------------------
        # Parse file
        # -----------------------
        parsed_data = parse_file(file.filename, content)

        # -----------------------
        # Map to SAP
        # -----------------------
        result = map_to_sap(parsed_data, target_schema, source_system)

        # -----------------------
        # RESPONSE FORMAT LAYER
        # -----------------------
        if mode == "raw":
            return {
                "status": "success",
                "file_name": file.filename,
                "target_schema": target_schema,
                "source_system": source_system,
                "data": result
            }

        # CAP mode (default) — keep response shape stable for CAP integration
        return {
            "value": result
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "file_name": file.filename
        }