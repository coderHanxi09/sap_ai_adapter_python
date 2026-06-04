from fastapi import FastAPI, UploadFile, File, HTTPException
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
    target_schema: str = "BusinessPartner"
):

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
        result = map_to_sap(parsed_data, target_schema)

        return {
            "value": result   # CAP-friendly format
        }

    except Exception as e:
        return {
            "error": str(e),
            "file_name": file.filename
        }