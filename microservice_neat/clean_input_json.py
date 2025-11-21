#!/usr/bin/env python3
"""Utility to normalize failed asset exports into valid JSON.

The raw exports shipped from Lima frequently contain:
  * bare string values (missing quotes)
  * JSON blobs stored as escaped strings inside the `metadata` field

This script fixes both issues so the rest of the tooling can safely read the
data.  It accepts either a single asset object or a list of assets and writes
the normalized output to the requested location.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable, List, Tuple, Union


def normalize_assets_file(
    input_path: str,
    output_path: str = "data/failed_assets_fixed.json",
    indent: int = 4,
) -> int:
    """Clean an input JSON file and write the normalized output.

    Returns the number of assets written so callers (including the API) can
    report progress without duplicating logic.
    """
    input_path = Path(input_path).expanduser()
    output_path = Path(output_path).expanduser()

    assets, original_type = load_assets(input_path)
    clean_assets(assets)
    write_assets(assets, output_path, original_type, indent)
    return len(assets)


def remove_trailing_commas(raw_text: str) -> str:
    """Strip trailing commas before } or ] blocks while respecting strings."""
    out: list[str] = []
    in_string = False
    escaped = False
    i = 0
    length = len(raw_text)

    while i < length:
        ch = raw_text[i]

        if in_string:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            i += 1
            continue

        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue

        if ch == ",":
            j = i + 1
            while j < length and raw_text[j].isspace():
                j += 1
            if j < length and raw_text[j] in "]}" :
                i += 1
                continue

        out.append(ch)
        i += 1

    return "".join(out)


def repair_top_level_fields(raw_text: str) -> str:
    """Normalize obvious issues (missing values, unquoted strings) on top-level lines."""
    fixed_lines: list[str] = []

    for line in raw_text.splitlines():
        match = re.match(r'^(\s*)"([^"]+)"\s*:\s*(.*)$', line)
        if not match:
            fixed_lines.append(line)
            continue

        indent, key, rest = match.groups()
        rest_stripped = rest.strip()

        has_comma = rest_stripped.endswith(",")
        if has_comma:
            rest_stripped = rest_stripped[:-1].rstrip()

        if not rest_stripped:
            value = '""'
        else:
            first = rest_stripped[0]
            lower = rest_stripped.lower()
            if lower in {"true", "false", "null"} or first in {'"', "{", "["}:
                value = rest_stripped
            else:
                try:
                    float(rest_stripped)
                    value = rest_stripped
                except ValueError:
                    escaped_val = rest_stripped.replace("\\", "\\\\").replace('"', '\\"')
                    value = f'"{escaped_val}"'

        newline = f'{indent}"{key}" : {value}'
        if has_comma:
            newline += ","
        fixed_lines.append(newline)

    return "\n".join(fixed_lines)


def repair_common_syntax(raw_text: str) -> str:
    """Apply a few lenient fixes to salvage slightly malformed JSON inputs."""
    text = remove_trailing_commas(raw_text)
    text = repair_top_level_fields(text)
    return text


def load_assets(path: Path) -> Tuple[List[dict], Union[type, None]]:
    """Load the raw assets, handling both single objects and lists."""
    raw_text = path.read_text(encoding="utf-8")
    fixed_text = repair_common_syntax(raw_text)

    try:
        data = json.loads(fixed_text)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Failed to parse {path}: {exc}") from exc

    if isinstance(data, list):
        return data, list
    if isinstance(data, dict):
        return [data], dict

    raise SystemExit(
        f"Expected a JSON object or list in {path}, received {type(data).__name__}"
    )


def decode_metadata_field(asset: dict) -> None:
    """Expand the stringified metadata blob into a proper object."""
    metadata = asset.get("metadata")
    if not isinstance(metadata, str):
        return

    metadata_str = metadata.strip()
    if not metadata_str:
        asset["metadata"] = {}
        return

    try:
        asset["metadata"] = json.loads(metadata_str)
    except json.JSONDecodeError as exc:
        asset_id = asset.get("entity_id") or asset.get("hardware_id")
        raise SystemExit(
            f"Unable to decode metadata for asset {asset_id!r}: {exc}"
        ) from exc


def clean_assets(assets: Iterable[dict]) -> None:
    for asset in assets:
        decode_metadata_field(asset)


def write_assets(
    assets: List[dict],
    output_path: Path,
    output_type: Union[type, None],
    indent: int,
) -> None:
    if output_type is dict:
        if len(assets) != 1:
            raise SystemExit(
                "Expected a single asset because the input JSON was an object."
            )
        to_dump: Union[List[dict], dict] = assets[0]
    else:
        to_dump = assets

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(to_dump, fh, indent=indent)
        fh.write("\n")
