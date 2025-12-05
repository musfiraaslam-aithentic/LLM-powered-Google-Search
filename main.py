from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

import tools

app = FastAPI(title="Asset Data Enrichment Service powered by AI Search Tools")


# default_tech_groups = tools.get_tech_groups()
# default_tech_types = tools.get_tech_types()


class ProcessRequest(BaseModel):
    metadata: Dict[str, Any]
    tech_groups: Optional[List[str]] = None
    tech_types: Optional[List[str]] = None


@app.get("/")
def read_root():
    return {"message": "Hello, FastAPI!"}

@app.get("/health")
def health() -> dict:
    return {"status": "ok"}

@app.post("/process")
def process_asset_endpoint(
    request: ProcessRequest
    ):
    metadata = request.metadata
    if not metadata:
        raise HTTPException(status_code=400, detail="metadata is required")

    processed_tech_groups = (
        tools.encode(request.tech_groups) if request.tech_groups else None
    )
    processed_tech_types = (
        tools.encode(request.tech_types) if request.tech_types else None
    )

    asset = {"metadata": metadata}

    # if tech_groups and len(tech_groups) > 0:
    #     processed_tech_groups = tools.encode(tech_groups)
    # else:
    #     processed_tech_groups = default_tech_groups

    # if tech_types and len(tech_types) > 0:
    #     processed_tech_types = tools.encode(tech_types)
    # else:
    #     processed_tech_types = default_tech_types

    try:
        result = tools.process_asset(asset, processed_tech_groups, processed_tech_types)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to process asset at this time: {exc}"
        ) from exc

    response = {
        "status": result.get("status"),
        "message": result.get("message"),
        "result": result.get("data")
    }

    return response
