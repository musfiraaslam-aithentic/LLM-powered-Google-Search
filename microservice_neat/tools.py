import json
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

# IMPORTANT FILES

TECH_GROUP_JSON = "data/tech_groups.json"
FAILED_ASSETS_JSON = "data/failed_assets_fixed.json"


# Models
gemini_models = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash", "gemini-flash-latest", "gemini-2.0-flash-001"]
groq_models = []

def countdown(minutes):
    total_seconds = minutes * 60
    while total_seconds:
        mins, secs = divmod(total_seconds, 60)
        timer = f"Cooldown Period {mins:02d}:{secs:02d}"
        print(timer, end='\r')  
        time.sleep(1)
        total_seconds -= 1
    print()  

def get_tech_groups():
    
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

    groq_prompt = ai_prompt(data)

    print("\nTrying Groq...")
    for attempt in range(1, 3):
        try:
            print(f"Groq attempt {attempt}/2...")
            return search_with_groq(groq_client, groq_prompt)
        except Exception as e:
            print(f"  Groq attempt {attempt} failed:", e)
            time.sleep(5)

    print("\nAll models failed.")
    return "Model failed to return response or is currently overloaded", []




# MAIN CODE TEST

output_folder = "output"
os.makedirs(output_folder, exist_ok=True)

# Load all failed assets
with open(FAILED_ASSETS_JSON, "r", encoding="utf-8") as f:
    assets = json.load(f)

# Load tech groups once
tech_groups = get_tech_groups()

for i, asset in enumerate(assets, start=1):

    output_path = os.path.join(output_folder, f"asset_{i}.json")

    # This code skips the asset if it already exists as a json to prevent overloading the model.
    if os.path.exists(output_path):
        print(f"Skipping Asset #{i} — {output_path} already exists.")
        continue


    print(f"\n--- Processing Asset #{i} ---\n")
    
    # Clean and encode asset data
    data = clean_asset_data(asset)
    response, urls = run_with_failover(data, tech_groups)
    
    # AI prompt adds tech groups
    #prompt = ai_prompt(data, tech_groups)

    # AI prompt only passes the failed asset data
    #prompt = ai_prompt(data)
    
    # Call Gemini model
    #response, urls = search_with_gemini(gemini_client, prompt, gemini_models[0])

    # Call Groq model
    #response, urls = search_with_groq(groq_client, prompt)

    #print(urls)
    
    # If you want groq to print score you can set this to True
    #print_results(response, urls, i, include_score=True)

    # Gemini does not have a score so you can print it like this or if you don't want groq score you can leave empty
    print_results(response, urls, i)

    # Save final_result to output/asset_X.json

    # Clean response text before parsing
    ai_json = parse_ai_json(response)
    if ai_json is None:
        print(f"Skipping Asset #{i} — invalid JSON from AI")
        continue

    merged_json = merge_reference_urls(ai_json, urls)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(merged_json, f, indent=4, ensure_ascii=False)

    print(f"Saved merged result to {output_path}")


    # Optional: pause to avoid hitting rate limits
    countdown(5)



