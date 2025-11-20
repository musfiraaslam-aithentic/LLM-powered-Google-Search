from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from clean_input_json import clean_assets as clean_assets_util, load_assets, write_assets
from tools import process_failed_assets

app = FastAPI(
    title="Asset Processing Service",
    version="1.0.0",
    description="Clean raw asset exports and process them with AI models.",
)


class CleanRequest(BaseModel):
    input_path: str = Field(..., description="Path to the raw JSON file (single asset or list).")
    output_path: str = Field(
        default="data/failed_assets_fixed.json",
        description="Destination for the normalized JSON.",
    )
    indent: int = Field(default=4, ge=0, description="Indentation level for the output JSON.")


class ProcessRequest(BaseModel):
    input_path: str = Field(default="data/failed_assets_fixed.json", description="Path to cleaned asset JSON.")
    output_dir: str = Field(default="output", description="Directory to write processed asset files.")
    cooldown_minutes: int = Field(default=0, ge=0, description="Minutes to wait between assets. Use 0 to disable.")
    limit: Optional[int] = Field(default=None, ge=1, description="Maximum assets to process.")
    overwrite: bool = Field(default=False, description="Rewrite outputs even if the file already exists.")


class PipelineRequest(BaseModel):
    raw_input_path: str = Field(..., description="Raw failed assets export path.")
    cleaned_output_path: str = Field(
        default="data/failed_assets_fixed.json",
        description="Where to write the normalized JSON before processing.",
    )
    output_dir: str = Field(default="output", description="Directory for processed asset files.")
    indent: int = Field(default=4, ge=0, description="Indentation level for the cleaned JSON file.")
    cooldown_minutes: int = Field(default=0, ge=0, description="Minutes to wait between assets. Use 0 to disable.")
    limit: Optional[int] = Field(default=None, ge=1, description="Maximum assets to process.")
    overwrite: bool = Field(default=False, description="Rewrite outputs even if the file already exists.")


def _clean_assets_file(input_path: str, output_path: str, indent: int) -> int:
    input_path = Path(input_path).expanduser()
    output_path = Path(output_path).expanduser()

    assets, original_type = load_assets(input_path)
    clean_assets_util(assets)
    write_assets(assets, output_path, original_type, indent)
    return len(assets)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/clean")
def clean_assets_endpoint(request: CleanRequest) -> dict:
    try:
        count = _clean_assets_file(request.input_path, request.output_path, request.indent)
    except Exception as exc:  # broad catch to surface model/log parsing errors to caller
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "records_written": count,
        "output_path": str(Path(request.output_path).expanduser()),
    }


@app.post("/process")
def process_assets(request: ProcessRequest) -> dict:
    try:
        summary = process_failed_assets(
            input_path=request.input_path,
            output_folder=request.output_dir,
            skip_existing=not request.overwrite,
            cooldown_minutes=request.cooldown_minutes,
            limit=request.limit,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "output_dir": str(Path(request.output_dir).expanduser()),
        "processed": summary["processed"],
        "errors": summary["errors"],
    }


@app.post("/pipeline")
def clean_then_process(request: PipelineRequest) -> dict:
    try:
        cleaned = _clean_assets_file(request.raw_input_path, request.cleaned_output_path, request.indent)
        summary = process_failed_assets(
            input_path=request.cleaned_output_path,
            output_folder=request.output_dir,
            skip_existing=not request.overwrite,
            cooldown_minutes=request.cooldown_minutes,
            limit=request.limit,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "cleaned_records": cleaned,
        "processing_summary": summary,
        "output_dir": str(Path(request.output_dir).expanduser()),
        "cleaned_output_path": str(Path(request.cleaned_output_path).expanduser()),
    }
