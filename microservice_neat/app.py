import json
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, File, Form, UploadFile, HTTPException

from clean_input_json import clean_assets as clean_assets_util, load_assets, write_assets
from tools import process_failed_assets, set_tech_groups_override

app = FastAPI(
    title="Asset Processing Service",
    description="Processes Failed Assets with AI Search Tools",
)


def _clean_assets_file(input_path: str, output_path: str, indent: int) -> int:
    """
    Cleans and normalizes asset JSON files using your existing cleaning logic.
    """
    input_path = Path(input_path).expanduser()
    output_path = Path(output_path).expanduser()

    assets, original_type = load_assets(input_path)
    clean_assets_util(assets)
    write_assets(assets, output_path, original_type, indent)
    return len(assets)


def _parse_tech_groups(raw_value: str) -> Optional[List[str]]:
    """
    Accepts either a JSON array string or a simple comma-separated list.
    Returns a list of tech groups or None if no value provided.
    """
    if not raw_value:
        return None

    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        # Fallback: allow comma-separated input for convenience
        parts = [item.strip() for item in raw_value.split(",") if item.strip()]
        if parts:
            return parts
        raise HTTPException(
            status_code=400,
            detail='tech_groups must be a valid JSON array or comma-separated list, e.g. ["Hardware","License"] or Hardware,License'
        )

    if not isinstance(parsed, list):
        raise HTTPException(
            status_code=400,
            detail="tech_groups must be a JSON array of strings"
        )

    return parsed


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}



@app.post("/upload_and_process")
async def upload_and_process(
    file: UploadFile = File(..., description="Upload the failed assets JSON file"),
    tech_groups: Optional[str] = Form(
        "",
        description='Optional list of tech groups as string (e.g. ["Hardware","License"])'
    ),
    overwrite: bool = Form(True),
    cooldown_minutes: int = Form(1),
    limit: Optional[int] = Form(None)
):
    """
    Upload a failed-assets JSON file, optionally supply custom tech groups.
    If tech_groups is not provided → default tech groups will be used.
    """
    try:
        # Save uploaded file
        input = Path("input/uploaded_failed_assets.json")
        contents = await file.read()

        input.write_text(contents.decode("utf-8"), encoding="utf-8")

        # Output cleaned file
        cleaned_output = Path("data/failed_assets_fixed.json")

        # Parse tech groups override if provided
        tech_group_list = None
        if tech_groups:
            try:
                tech_group_list = _parse_tech_groups(tech_groups)
                set_tech_groups_override(tech_group_list)
            except Exception:
                raise HTTPException(
                    status_code=400,
                    detail='tech_groups must be a valid JSON array or comma-separated list, e.g. ["Hardware","License"] or Hardware,License'
                )

        # Clean uploaded file
        cleaned_count = _clean_assets_file(
            str(input),
            str(cleaned_output),
            indent=4
        )

        # Process cleaned assets
        summary = process_failed_assets(
            input_path=str(cleaned_output),
            output_folder="output",
            skip_existing=not overwrite,
            cooldown_minutes=cooldown_minutes,
            limit=limit,
        )

        # Load processed asset data into response payload
        processed_assets = []
        load_errors = []
        for path in summary.get("processed", []):
            try:
                data = json.loads(Path(path).read_text(encoding="utf-8"))
                processed_assets.append({"path": str(path), "data": data})
            except Exception as exc:
                load_errors.append({"path": str(path), "error": str(exc)})

        return {
            "uploaded_records": cleaned_count,
            "processing_summary": summary,
            "cleaned_output_path": str(cleaned_output),
            "processed_assets": processed_assets,
            "output_load_errors": load_errors,
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
