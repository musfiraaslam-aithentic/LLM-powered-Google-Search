from fastapi import FastAPI, Body
import tools
import json

app = FastAPI()

tech_groups = tools.get_tech_groups()


@app.get("/")
def read_root():
    return {"message": "Hello, FastAPI!"}


@app.post("/process")
def process_asset_endpoint(asset_data: dict = Body(...)):

    asset, errors = tools.validate_asset(asset_data)

    if errors:
        return {
            "status": "failed",
            "message": "Asset schema is not correct",
            #"errors": errors
        }

    result = tools.process_asset(asset_data, tech_groups)

    return {
        "status": "success",
        "result": result
    }
