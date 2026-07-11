import json

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from ai_mapper import map_to_sap
from parser import parse_file

app = FastAPI(title="SAP AI Adapter Service")


def _log_block(title: str, payload) -> None:
    """Pretty-print a labeled JSON block to stdout for live terminal viewing."""
    try:
        body = json.dumps(payload, indent=2, ensure_ascii=False)
    except (TypeError, ValueError):
        body = str(payload)
    print(f"\n===== {title} =====", flush=True)
    print(body, flush=True)


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
    try:
        # File size safety check (10MB limit)
        content = await file.read()
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="File too large")

        # Parse file
        try:
            parsed_data = parse_file(file.filename, content)
            record_in = len(parsed_data) if hasattr(parsed_data, "__len__") else "N/A"
            print(
                f"\n>>> UPLOAD {file.filename} | schema={target_schema} "
                f"| source={source_system} | mode={mode} | records={record_in}",
                flush=True,
            )
            _log_block("PARSED INPUT", parsed_data)
        except Exception as e:
            raise HTTPException(
                status_code=422,
                detail={
                    "status": "FAILED",
                    "errorType": "PARSE_ERROR",
                    "message": f"Failed to parse file: {str(e)}",
                    "fileName": file.filename
                }
            )

        # Map to SAP
        try:
            result = map_to_sap(parsed_data, target_schema, source_system)
            _log_block(f"MAPPING RESULT ({target_schema})", result)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail={
                    "status": "FAILED",
                    "errorType": "MAPPING_ERROR",
                    "message": f"AI mapping failed: {str(e)}",
                    "fileName": file.filename
                }
            )

        # Calculate record count
        record_count = len(result) if isinstance(result, list) else 1

        if mode == "raw":
            return {
                "status": "Completed",
                "fileName": file.filename,
                "recordCount": record_count,
                "targetSchema": target_schema,
                "sourceSystem": source_system,
                "result": result
            }

        # CAP mode (default)
        return {
            "status": "Completed",
            "fileName": file.filename,
            "recordCount": record_count,
            "value": result
        }

    except HTTPException:
        raise  

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "status": "FAILED",
                "errorType": "INTERNAL_ERROR",
                "message": str(e),
                "fileName": file.filename
            }
        )