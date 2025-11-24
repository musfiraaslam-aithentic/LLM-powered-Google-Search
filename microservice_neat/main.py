from fastapi import FastAPI, Body
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import tools
import json

app = FastAPI()

default_tech_groups = tools.get_tech_groups()

class ProcessRequest(BaseModel):
    metadata: Dict[str, Any]
    tech_groups: Optional[List[str]] = None


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

    if tech_groups and len(tech_groups) > 0:
        processed_tech_groups = tools.encode(tech_groups)
    else:
        processed_tech_groups = default_tech_groups

    print("Incoming metadata:", metadata)

    asset = {"metadata": metadata}
    result = tools.process_asset(asset, processed_tech_groups)

    return {
        "status": "success",
        "result": result
    }
