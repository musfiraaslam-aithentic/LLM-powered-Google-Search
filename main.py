from fastapi import FastAPI, Body
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import tools
import json


app = FastAPI(
    title="Asset Data Enrichment Service powered by AI Search Tools"
    )

default_tech_groups = tools.get_tech_groups()
default_tech_types = tools.get_tech_types()


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
def process_asset_endpoint(request: ProcessRequest):
    metadata = request.metadata
    tech_groups = request.tech_groups
    tech_types = request.tech_types

    processed_tech_groups = tools.encode(tech_groups) if tech_groups else None
    processed_tech_types = tools.encode(tech_types) if tech_types else None
    
    # if tech_groups and len(tech_groups) > 0:
    #     processed_tech_groups = tools.encode(tech_groups)
    # else:
    #     processed_tech_groups = default_tech_groups

    if tech_types and len(tech_types) > 0:
        processed_tech_types = tools.encode(tech_types)
    else:
        processed_tech_types = default_tech_types

    print("Incoming metadata:", metadata)

    asset = {"metadata": metadata}
    result = tools.process_asset(asset, processed_tech_groups, processed_tech_types)

    # return {
    #     "status": "success",
    #     "result": result
    # }
    return {
        "status": result.get("status"),
        "message": result.get("message"),
        "result": result.get("data")
    }
