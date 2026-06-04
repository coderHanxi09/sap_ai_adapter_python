from fastapi import FastAPI, UploadFile, File
from ai_mapper import map_to_sap
from parser import parse_file


app = FastAPI(title="SAP AI Adapter Service")


# Health check endpoint
@app.get("/")
def health():
    return {"status": "running"}


# NOTE: the `/map` endpoint was removed because it's not used by the CAP flow.


# File upload endpoint (CSV / JSON / TXT)
@app.post("/upload")
async def upload_file(file: UploadFile = File(...), target_schema: str = "BusinessPartner"):

    content = await file.read()

    parsed_data = parse_file(file.filename, content)

    result = map_to_sap(parsed_data, target_schema)

    # return plain JSON so CAP can consume mapped data directly
    return {
        "status": "success",
        "file_name": file.filename,
        "target_schema": target_schema,
        "mapped_result": result
    }