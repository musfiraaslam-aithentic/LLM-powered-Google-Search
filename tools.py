import json
from google import genai
from google.genai import types
from groq import Groq
import os
from dotenv import load_dotenv 
import time
import re
from toon import encode
from datetime import datetime, timedelta


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

# TECH_GROUP_JSON = "data/tech_groups.json"
# FAILED_ASSETS_JSON = "data/failed_assets_fixed.json"
# MONITOR_REQUESTS = "requests.json"  #I thought this could break across different platforms (Windows/Linux)

TECH_GROUP_JSON = os.path.join("data", "tech_groups.json")
FAILED_ASSETS_JSON = os.path.join("data", "failed_assets_fixed.json")
MONITOR_REQUESTS = os.path.join("logs", "requests.json") # I think this should be inside separata Logs folder

# Models
gemini_models = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash", "gemini-flash-latest", "gemini-2.0-flash-001"]
#locked_models = []
#groq_models = []

def track_model_requests(model_name: str):

    if not os.path.exists(MONITOR_REQUESTS):
        data = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "models": {}
        }
    else:
        with open(MONITOR_REQUESTS, "r") as f:
            data = json.load(f)

    # Check if a reset is needed (24h)
    saved_date = datetime.strptime(data["date"], "%Y-%m-%d")
    now = datetime.now()

    if (now - saved_date) >= timedelta(days=1):
        # Reset the whole file
        data = {
            "date": now.strftime("%Y-%m-%d"),
            "models": {}
        }


    if model_name not in data["models"]:
        data["models"][model_name] = 1
    else:
        data["models"][model_name] += 1

    with open(MONITOR_REQUESTS, "w") as f:
        json.dump(data, f, indent=4)


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
    metadata = asset.get("metadata") or {}

    cleaned = metadata

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

    track_model_requests(model)

    reference_urls = gemini_reference_urls(response)

    return response.text, reference_urls 

def search_with_groq(client, prompt, instructions="", model="groq/compound", max_completion_tokens=1024):

    #print("Groq Model Being Used", model)

    # If using compound model → enable web tools
    if model == "groq/compound":
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": prompt}
            ],
            temperature=1,
            max_completion_tokens=max_completion_tokens,
            top_p=1,
            stream=False,
            stop=None,
            compound_custom={"tools":{"enabled_tools":["web_search","visit_website"]}}
        )
    else:
       completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": prompt}
            ],
            temperature=1,
            max_completion_tokens=max_completion_tokens,
            top_p=1,
            stream=False,
            stop=None,

        )
       
    track_model_requests(model)
    response = completion.choices[0].message.content

    # Lists any executed tools
    tools_used = None
    if completion.choices[0].message.executed_tools: 
        tools_used = completion.choices[0].message.executed_tools[0].search_results

    reference_urls = groq_reference_urls(tools_used)

    return response, reference_urls


def ai_prompt(asset_data, tech_groups=None, tech_types=None):

    # if tech_groups:
    #     tech_groups_text = f"Fill this field using this list: {tech_groups}. If it is not a list and there is only one tech group set that as the tech group."
    # else:
    #     tech_groups_text = "Fill this field with the appropriate tech group"
    
    if not tech_groups:
        tech_group_text = "No tech group list was provided. Return \"null\" for tech_group."
    else:
        tech_group_text = (
            f"Fill this field using this list: {tech_groups}. "
            f"If the value does not match any item in the list, return \"null\"."
        )

    if not tech_types:
        tech_type_text = "No tech type list was provided. Return \"null\" for tech_type."
    else:
        tech_type_text = (
            f"Choose one and fill this field using this list: {tech_types}. "
            f"If the value does not match any item in the list, return \"null\"."
        )

    prompt = f"""

        The data provided is of an asset which we were unable to match or identify.

        This is the data we received:
            {asset_data}

        Using this data, Do the Internet Search to find the exact model. 

        ** If the data is not specific enough to a particular model, return: "Data is not specific" **
        ** If the data is not specific enough to a particular model, do not return the json **

        If you are unable to find the exact model, find the closest results.

        Return these pieces of data in JSON format:

        Brand/Manufacturer/Vendor: (e.g. Apple or ASUS) || null
        Brand Country: (e.g. United States) || null
        Brand Domain: (e.g. https://www.asus.com/ or https://www.apple.com/) || null
        Tech Type: {tech_type_text}
        Tech Group: {tech_group_text}

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

def run_with_failover(data, tech_groups, tech_types):
    gemini_prompt = ai_prompt(data, tech_groups, tech_types)

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
        reduced_prompt = ai_prompt(data, tech_group_guess, tech_types)

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
        reduced_prompt = ai_prompt(data, tech_group_guess, tech_types)
        countdown(3)

        return search_with_groq(groq_client, reduced_prompt)

    except Exception as e:
        print("  Groq-only fallback failed:", e)

    print("\nAll models failed.")
    return "Model failed to return response or is currently overloaded", []


def process_asset(asset, tech_groups, tech_types):

    print("Processing Asset Data")

    cleaned_data = clean_asset_data(asset)

    if not cleaned_data:
        return {
            "status": "failure",
            "message": "Input asset data is invalid or missing.",
            "data": {}
        }
    print("Cleaned data sent to AI:", cleaned_data)

    response_text, urls = run_with_failover(cleaned_data, tech_groups, tech_types)

    if response_text is None:
        return {
            "status": "failure",
            "message": "AI model failed. Please try again later",
            "data": {}
        }

    if isinstance(response_text, str) and response_text.strip().lower() == "data is not specific":
        return {
            "status": "failure",
            "message": "Data is not specific enough to identify the product.",
            "data": {}
        }

    ai_json = parse_ai_json(response_text)
    if ai_json is None:
        return {
            "status": "failure",
            "message": "AI returned invalid response. Please try again",
            "data": {}
        }

    merged_json = merge_reference_urls(ai_json, urls)
    
    print(response_text)
    print(urls)

    tech_group = merged_json.get("tech_group")
    tech_type = merged_json.get("tech_type")

    missing_group = tech_group in (None, "", "null", "Not Found")
    missing_type = tech_type in (None, "", "null", "Not Found")

    # Both are missing
    if missing_group and missing_type:
        return {
            "status": "success",
            "message": "Asset enriched, but no matching tech group and tech type were found in the provided lists.",
            "data": merged_json
        }

    # Only tech group missing
    if missing_group:
        return {
            "status": "success",
            "message": "Asset enriched, but no matching tech group was found in the provided Tech Groups list.",
            "data": merged_json
        }

    # Only tech type missing
    if missing_type:
        return {
            "status": "success",
            "message": "Asset enriched, but no matching tech type was found in the provided Tech Types list.",
            "data": merged_json
        }


    return {
        "status": "success",
        "message": "Asset successfully enriched.",
        "data": merged_json
    }