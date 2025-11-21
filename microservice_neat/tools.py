import json
from pathlib import Path
from typing import Any, Optional
from google import genai
from google.genai import types
from groq import Groq
import os
from dotenv import load_dotenv 
import time
import re
from toon import encode
from datetime import datetime, timedelta, timezone

# Load environment variables
load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Initialize Clients Once
gemini_client = genai.Client()

groq_client = Groq(
    api_key=os.getenv("GROQ_API_KEY"),
    default_headers={
        "Groq-Model-Version": "latest",
    }
)

LOG_DIR = Path("logs")
TECH_GROUP_JSON = Path("data/tech_groups.json")
FAILED_ASSETS_JSON = Path("data/failed_assets_fixed.json")
MODEL_USAGE_LOG = LOG_DIR.joinpath("model_usage.log") 
REQUESTS_JSON = LOG_DIR.joinpath("daily_model_requests.json") 

# Models
gemini_models = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash", "gemini-flash-latest", "gemini-2.0-flash-001"]
groq_models = []

# Model usage tracker
model_usage = {
    "gemini": {},
    "groq": {},
}
_tech_groups_override: Optional[Any] = None


def _load_request_log():
    """Load or initialize the per-day request counter file."""
    source_path = REQUESTS_JSON 
    if not source_path.exists():
        return {"today": {}}

    try:
        data = json.loads(source_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"today": {}}

    # Normalize the daily structure to include providers
    normalized_daily = {}
    for day, counts in (data.get("today") or {}).items():
        if not isinstance(counts, dict):
            normalized_daily[day] = {}
            continue

        normalized_daily[day] = {}
        is_provider_scoped = all(isinstance(v, dict) for v in counts.values()) and bool(counts)
        if is_provider_scoped:
            for provider, models in counts.items():
                if not isinstance(models, dict):
                    continue
                normalized_daily[day][provider] = {
                    model: count for model, count in models.items() if isinstance(count, int)
                }
            continue

        for model, count in counts.items():
            if not isinstance(count, int):
                continue

            # Getting provider name for logs
            lowered = (model or "").lower()
            if lowered.startswith("gemini") or model in gemini_models:
                provider= "gemini"
            if model in groq_models or "/" in model:
                provider= "groq"
     
            provider_bucket = normalized_daily[day].setdefault(provider, {})
            provider_bucket[model] = count

    data["today"] = normalized_daily
    return data




def _save_request_log(data):
    """Persist per-day request counters."""
    REQUESTS_JSON.parent.mkdir(parents=True, exist_ok=True)
    REQUESTS_JSON.write_text(json.dumps(data, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")


def update_daily_request_log(provider, model_name):
    """Increment the per-day counter for the given model."""
    today = datetime.now(timezone.utc).date().isoformat()
    data = _load_request_log()
    daily = data.setdefault("daily", {})
    by_day = daily.setdefault(today, {})
    provider_key = (provider or "unspecified").lower()
    models_for_provider = by_day.setdefault(provider_key, {})
    models_for_provider[model_name] = models_for_provider.get(model_name, 0) + 1
    data["last_update"] = datetime.now(timezone.utc).isoformat()
    _save_request_log(data)


def track_model_usage(provider, model_name):
    """
    Track how many times each model is invoked.

    Args:
        provider (str): Provider name, e.g., "gemini" or "groq".
        model_name (str): Specific model identifier.
    """
    if not provider or not model_name:
        return

    provider_key = provider.lower()
    provider_usage = model_usage.setdefault(provider_key, {})
    provider_usage[model_name] = provider_usage.get(model_name, 0) + 1

    # Persist per-model daily counts to JSON
    update_daily_request_log(provider_key, model_name)

    # Persist usage entry to log file
    MODEL_USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).isoformat()
    log_entry = f"{timestamp} | provider={provider_key} | model={model_name} | count={provider_usage[model_name]}\n"
    try:
        with open(MODEL_USAGE_LOG, "a", encoding="utf-8") as log_file:
            log_file.write(log_entry)
    except OSError as e:
        print(f"Failed to write model usage log: {e}")



def countdown(minutes):
    total_seconds = minutes * 60
    while total_seconds:
        mins, secs = divmod(total_seconds, 60)
        timer = f"Cooldown Period {mins:02d}:{secs:02d}"
        print(timer, end='\r')  
        time.sleep(1)
        total_seconds -= 1
    print()  

def set_tech_groups_override(tech_groups: Any) -> Any:
    """Set an in-memory override for tech groups."""
    global _tech_groups_override
    _tech_groups_override = tech_groups
    return _tech_groups_override


def get_tech_groups():
    """Return encoded tech groups, preferring any provided override."""
    if _tech_groups_override is not None:
        return encode(_tech_groups_override)

    with open(TECH_GROUP_JSON, "r") as f:
        data = json.load(f)

    TECH_GROUPS = data["TECH_GROUPS"]
    toon_tech_groups = encode(TECH_GROUPS)

    return toon_tech_groups

def clean_asset_data(asset):
    # Extract core fields
    model = asset.get("MODEL") or ""
    manufacturer = asset.get("MANUFACTURER") or ""
    metadata = asset.get("metadata") or {}

    cleaned = {
        "model": model,
        "manufacturer": manufacturer,
        "metadata": metadata
    }

    toon_asset_data = encode(cleaned)

    return toon_asset_data


def print_results(text, refs, id, include_score=False):
   
    print(f"\n=== Response for asset #{id} ===\n")
    print(text.strip())

    print("\n=== Reference Urls ===")
    if not refs:
        print("(No reference URLs returned.)\n")
        return

    print()
    for idx, ref in enumerate(refs, start=1):
        if include_score and "score" in ref:
            print(f"[{idx}] {ref['title']} - {ref['url']} (score: {ref['score']})")
        else:
            print(f"[{idx}] {ref['title']} - {ref['url']}")



def gemini_reference_urls(response):
    grounding_metadata = getattr(response.candidates[0], "grounding_metadata", None)
    if grounding_metadata is None:
        return []

    supports = getattr(grounding_metadata, "grounding_supports", []) or []
    chunks = getattr(grounding_metadata, "grounding_chunks", []) or []

    refs = []
    for support in supports:
        for i in getattr(support, "grounding_chunk_indices", []):
            if i < len(chunks):
                uri = getattr(chunks[i].web, "uri", "")
                title = getattr(chunks[i].web, "title", uri)

                if uri:
                    refs.append({
                        "title": title,
                        "url": uri
                    })

    seen = set()
    unique_refs = []
    for ref in refs:
        if ref["url"] not in seen:
            seen.add(ref["url"])
            unique_refs.append(ref)

    return unique_refs

def groq_reference_urls(tool_results):
    if not tool_results or not tool_results.results:
        return []

    # This portion sorts links from highest to lowest confidence score
    results_sorted = sorted(
        tool_results.results,
        key=lambda r: r.score,
        reverse=True
    )

    refs = []
    for r in results_sorted:
        refs.append({
            "title": r.title,
            "url": r.url,
            "score": r.score
        })

    return refs



def search_with_gemini(client, prompt, model):

    track_model_usage("gemini", model)

    # Enable Google Search tool
    grounding_tool = types.Tool(
        google_search=types.GoogleSearch()
    )

    # Configure generation with the grounding tool
    config = types.GenerateContentConfig(
        tools=[grounding_tool]
    )

    #print("Gemini Model Being Used", model)

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=config,
    )

    reference_urls = gemini_reference_urls(response)

    return response.text, reference_urls

def search_with_groq(client, prompt, instructions="", model="groq/compound"):

    track_model_usage("groq", model)

    #print("Groq Model Being Used", model)

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": instructions},
            {"role": "user", "content": prompt}
        ],
        temperature=1,
        max_completion_tokens=1024,
        top_p=1,
        stream=False,
        stop=None,
        compound_custom={"tools":{"enabled_tools":["web_search","visit_website"]}}
    )

    response = completion.choices[0].message.content

    # Lists any executed tools
    tools_used = None
    if completion.choices[0].message.executed_tools: 
        tools_used = completion.choices[0].message.executed_tools[0].search_results

    reference_urls = groq_reference_urls(tools_used)

    return response, reference_urls


def ai_prompt(asset_data, tech_groups=None):

    if tech_groups:
        tech_groups_text = f"Fill this field using this list: {tech_groups}"
    else:
        tech_groups_text = "Fill this field with the appropriate tech group"

    prompt = f"""

        The data provided is of an asset which we were unable to match or identify.

        This is the data we received:
            {asset_data}

        Using this data, help to find the exact model. 

        ** If the data is not specific enough to a particular model, return: "data is not specific" **
        ** If the data is not specific enough to a particular model, do not return the json **

        If you are unable to find the exact model, find the closest results.

        Return these pieces of data in JSON format:

        Brand/Manufacturer/Vendor: (e.g. Apple or ASUS) || null
        Brand Country: (e.g. United States) || null
        Brand Domain: (e.g. https://www.asus.com/ or https://www.apple.com/) || null
        Tech Type: Choose one and fill this field using this list: "Hardware", "License", "Subscription", "Maintenance", "Virtual Machines", "Freeware", "Certificate" 
        Tech Group: {tech_groups_text}

        Product SKU/ID: || null
        Product Description: || null
        Product Features: List **exactly 5 features or more**, and use **descriptive keys** for each (e.g., "CPU", "RAM", "Display", "Storage", "Battery") || null

        Make sure to fill the JSON and enrich the data.

        Use the following template (double braces {{ }} are used to escape braces in f-strings):

        {{
            "brand": "",
            "brand_country": "",
            "brand_domain": "",
            "tech_group": "",
            "tech_type": "",
            "product_id": "",
            "product_desc": "",
            "product_features": {{}}
            "reference_urls": []
        }}

        ** Give response strictly in json format **
        ** leave reference_urls field empty **

        """

    return prompt

def parse_ai_json(response_text):
    clean_response = response_text.strip()

    # Remove code block markers if present
    if clean_response.startswith("```json"):
        clean_response = clean_response[len("```json"):].strip()
    elif clean_response.startswith("```"):
        clean_response = clean_response[3:].strip()
    if clean_response.endswith("```"):
        clean_response = clean_response[:-3].strip()

    # Extract JSON object
    match = re.search(r"\{.*\}", clean_response, re.DOTALL)
    if not match:
        return None

    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None




def tech_group_prompt(cleaned_asset_data, tech_groups):

    prompt = f"""
        The data provided is of an asset which we were unable to match or identify.

        This is the data we received:
            {cleaned_asset_data}

        From the following list of tech groups, choose the **one group** that best represents the asset.
        - Return **exactly one value** from the list.
        - If there is not enough information, return **null**.
        - Return **only the chosen value**, no explanations or extra text.

        ** Your response should be 5 words or less **
        ** If tech group can't be determined, return "Not Found" **

        {tech_groups}
    """

    return prompt

def merge_reference_urls(ai_json, urls):
    if ai_json is None:
        return None
    ai_json["reference_urls"] = urls or []
    return ai_json

def run_with_failover(data, tech_groups):
    gemini_prompt = ai_prompt(data, tech_groups)

    for model in gemini_models:
        print(f"\nTrying Gemini model: {model}")
        for attempt in range(1, 3):
            try:
                print(f"Attempt {attempt}/2...")
                return search_with_gemini(gemini_client, gemini_prompt, model)
            except Exception as e:
                print(f"  Gemini '{model}' attempt {attempt} failed:", e)
                time.sleep(5)
        print("  Switching to next Gemini model in 10 seconds...")
        time.sleep(10)

    try:
        print("\nGemini full failure — using Groq (70B) to reduce prompt size...")
        tech_group_guess, _ = search_with_groq(
            groq_client,
            tech_group_prompt(data, tech_groups),
            model="llama-3.3-70b-versatile",
            max_completion_tokens=5
        )

        print("Groq Tech Group Guess:", tech_group_guess)
        reduced_prompt = ai_prompt(data, tech_group_guess)

        for model in gemini_models:
            print(f"\nTrying reduced Gemini prompt with model: {model}")
            try:
                return search_with_gemini(gemini_client, reduced_prompt, model)
            except Exception as e:
                print(f"  Reduced Gemini '{model}' attempt failed:", e)
            print("  Switching to next Gemini model in 10 seconds...")
            time.sleep(10)

    except Exception as e:
        print("Reduced Gemini fallback failed:", e)

    print("\nTrying Groq-only fallback...")
    try:
        tech_group_guess, _ = search_with_groq(
            groq_client,
            tech_group_prompt(data, tech_groups),
            model="llama-3.3-70b-versatile",
            max_completion_tokens=5
        )

        print("Groq Tech Group Guess (final stage):", tech_group_guess)
        reduced_prompt = ai_prompt(data, tech_group_guess)
        countdown(3)

        return search_with_groq(groq_client, reduced_prompt)

    except Exception as e:
        print("  Groq-only fallback failed:", e)

    print("\nAll models failed.")
    return "Model failed to return response or is currently overloaded", []

def process_failed_assets(
    input_path: str = FAILED_ASSETS_JSON,
    output_folder: str = "output",
    skip_existing: bool = False,
    cooldown_minutes: int = 2,
    limit: Optional[int] = None,
):
    """Process failed assets and write output JSON files."""
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    os.makedirs(output_folder, exist_ok=True)

    with open(input_path, "r", encoding="utf-8") as f:
        assets = json.load(f)

    tech_groups = get_tech_groups()
    processed, errors = [], []

    for i, asset in enumerate(assets, start=1):
        if limit is not None and len(processed) >= limit:
            break

        output_path = os.path.join(output_folder, f"asset_{i}.json")

        if skip_existing and os.path.exists(output_path):
            print(f"Skipping Asset #{i} — {output_path} already exists.")
        
            continue

        print(f"\n--- Processing Asset #{i} ---\n")

        data = clean_asset_data(asset)
        response, urls = run_with_failover(data, tech_groups)
        print_results(response, urls, i)

        ai_json = parse_ai_json(response)
        if ai_json is None:
            msg = "invalid JSON from AI"
            print(f"Skipping Asset #{i} — {msg}")
            errors.append({"index": i, "path": output_path, "error": msg})
            continue

        merged_json = merge_reference_urls(ai_json, urls)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(merged_json, f, indent=4, ensure_ascii=False)

        print(f"Saved merged result to {output_path}")
        processed.append(output_path)

        if cooldown_minutes:
            countdown(cooldown_minutes)

    return {"processed": processed, "errors": errors}


if __name__ == "__main__":
    input_path = FAILED_ASSETS_JSON
    output_dir = "output"
    overwrite = False
    cooldown_minutes = 1

    try:
        summary = process_failed_assets(
            input_path=input_path,
            output_folder=output_dir,
            skip_existing=not overwrite,
            cooldown_minutes=cooldown_minutes,
        )
    except Exception as exc:
        print(f"Processing failed: {exc}")
        raise SystemExit(1) from exc

    print(
        f"Processing complete. "
        f"Processed: {len(summary['processed'])}, "
        f"Errors: {len(summary['errors'])}"
    )
