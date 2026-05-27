from fastapi import FastAPI, UploadFile, File
import json
from ai_mapper import map_to_sap
from parser import parse_file
from fastapi.responses import StreamingResponse
import io


app = FastAPI(title="SAP AI Adapter Service")


# Health check endpoint
@app.get("/")
def health():
    return {"status": "running"}


# JSON input endpoint
@app.post("/map")
def map_json(data: dict, target_schema: str = "BusinessPartner"):

    result = map_to_sap(data, target_schema)

    return {
        "status": "success",
        "mapped_result": result
    }


# File upload endpoint (CSV / JSON / TXT)
@app.post("/upload")
async def upload_file(file: UploadFile = File(...), target_schema: str = "BusinessPartner"):

    content = await file.read()

    parsed_data = parse_file(file.filename, content)

    result = map_to_sap(parsed_data, target_schema)

    # return as downloadable JSON file
    out = io.BytesIO()
    out.write(json.dumps({"filename": file.filename, "mapped_result": result}, ensure_ascii=False, indent=2).encode())
    out.seek(0)

    return StreamingResponse(out, media_type="application/json", headers={
        "Content-Disposition": f"attachment; filename=map_{file.filename}.json"
    })