import json
from pathlib import Path
from google import genai
import os
from dotenv import load_dotenv 
import time
import re
from difflib import get_close_matches
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from typing import Optional
import requests
from groq import Groq
from urllib3 import Retry

# Load environment variables
load_dotenv()
API_KEY_ENV_VARS = ["GOOGLE_API_KEY_1", "GOOGLE_API_KEY_2"]
AVAILABLE_API_KEYS: list[str] = []
for var in API_KEY_ENV_VARS:
    value = os.getenv(var)
    if value and value not in AVAILABLE_API_KEYS:
        AVAILABLE_API_KEYS.append(value)

if not AVAILABLE_API_KEYS:
    raise SystemExit("No Google API keys set in environment!")


def build_client(api_key: str) -> genai.Client:
    return genai.Client(api_key=api_key)


CURRENT_API_KEY_INDEX = 0
client = build_client(AVAILABLE_API_KEYS[CURRENT_API_KEY_INDEX])

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if GROQ_API_KEY:
    groq_client = Groq(
        api_key=GROQ_API_KEY,
        default_headers={"Groq-Model-Version": "latest"},
    )
else:
    groq_client = None

BASE_DIR = Path(__file__).resolve().parent


TECH_GROUPS_FILE = BASE_DIR.joinpath("tech_groups.txt")
TECH_TYPES_FILE = BASE_DIR.joinpath("tech_types.txt")
SECOND_LEVEL_TREE_FILE = BASE_DIR.joinpath("second_level_tree.json")
TECHGROUP_JSON_DIR = BASE_DIR.joinpath("techgroup_jsons")
METDATA_FILE = BASE_DIR.joinpath("metadata.json")
OUTPUT_DIR = BASE_DIR.joinpath("output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

REQUEST_TRACKING_FILE = BASE_DIR.joinpath("requests.json")
REQUESTS_PER_DAY = 250

FLASH_MODEL = "gemini-2.5-flash"
PRO_MODEL = "gemini-2.5-pro"
MODEL_LIMITS = {
    FLASH_MODEL: 250,
    PRO_MODEL: 200,
}
CURRENT_MODEL = FLASH_MODEL
FAIL_THRESHOLD = 1
FAILURE_COUNTS = {
    FLASH_MODEL: 0,
    PRO_MODEL: 0,
}
DEFAULT_DELAY_AFTER_REQUEST = 30.0
API_KEY_FAIL_THRESHOLD = 1
API_KEY_FAILURE_COUNTS = [0] * len(AVAILABLE_API_KEYS)
GROQ_USAGE_LOG = BASE_DIR.joinpath("groq_usage.json")
GROQ_DAILY_CALL_LIMIT = 250
PROVIDER_NAMES = ["gemini"]
if groq_client:
    PROVIDER_NAMES.append("groq")
ACTIVE_PROVIDER_INDEX = 0 # for Gemini set it to 0, for Groq set it to 1
PROVIDER_FAILURE_COUNTS = {name: 0 for name in PROVIDER_NAMES}
PROVIDER_FAIL_THRESHOLD = 1


def load_request_tracking() -> dict:
    """Load or initialize request tracking JSON."""
    if not REQUEST_TRACKING_FILE.exists():
        data = {
            "model_counts": {model: 0 for model in MODEL_LIMITS},
            "last_reset_date": datetime.now(timezone.utc).isoformat(),
        }
        save_request_tracking(data)
        return data
    with REQUEST_TRACKING_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)

    # Backward compatibility for older format
    if "model_counts" not in data:
        total = data.get("total_requests_tracked", 0)
        data["model_counts"] = {model: 0 for model in MODEL_LIMITS}
        data["model_counts"][FLASH_MODEL] = total
        data.pop("total_requests_tracked", None)
        save_request_tracking(data)

    for model in MODEL_LIMITS:
        data["model_counts"].setdefault(model, 0)

    return data


def save_request_tracking(data: dict) -> None:
    with REQUEST_TRACKING_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def reset_daily_if_needed() -> dict:
    """Reset request count if 24+ hours have passed."""
    data = load_request_tracking()
    last_reset = datetime.fromisoformat(data["last_reset_date"])
    now = datetime.now(timezone.utc)
    if now - last_reset >= timedelta(hours=24):
        data["model_counts"] = {model: 0 for model in MODEL_LIMITS}
        data["last_reset_date"] = now.isoformat()
        save_request_tracking(data)
    return data


def record_request(model_name: str) -> None:
    """Persist a successful request count for the given model."""
    data = reset_daily_if_needed()
    data["model_counts"][model_name] = data["model_counts"].get(model_name, 0) + 1
    save_request_tracking(data)
    limit = MODEL_LIMITS.get(model_name, MODEL_LIMITS[FLASH_MODEL])
    print(f"Total API Requests Today for {model_name}: {data['model_counts'][model_name]}/{limit}")


def choose_model(preferred_model: str) -> str:
    """Return the best model to use based on daily limits, preferring the requested one."""
    if preferred_model not in MODEL_LIMITS:
        preferred_model = FLASH_MODEL

    data = reset_daily_if_needed()
    if preferred_model == PRO_MODEL:
        candidate_order = [PRO_MODEL, FLASH_MODEL]
    else:
        candidate_order = [FLASH_MODEL, PRO_MODEL]

    for model_name in candidate_order:
        count = data["model_counts"].get(model_name, 0)
        limit = MODEL_LIMITS.get(model_name, MODEL_LIMITS[FLASH_MODEL])
        if count < limit:
            if model_name != preferred_model:
                print(f"{preferred_model} quota reached. Switching to {model_name}.")
            return model_name

    raise RuntimeError("Daily request limit exceeded for all available models.")


def switch_api_key() -> None:
    """Rotate to the next available API key."""
    global CURRENT_API_KEY_INDEX, client
    if len(AVAILABLE_API_KEYS) <= 1:
        print("Only one API key configured; cannot switch API keys.")
        return

    CURRENT_API_KEY_INDEX = (CURRENT_API_KEY_INDEX + 1) % len(AVAILABLE_API_KEYS)
    client = build_client(AVAILABLE_API_KEYS[CURRENT_API_KEY_INDEX])
    print(f"Switched to API key #{CURRENT_API_KEY_INDEX + 1}")


def load_groq_usage() -> dict:
    if not GROQ_USAGE_LOG.exists():
        return {}
    with GROQ_USAGE_LOG.open("r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def save_groq_usage(data: dict) -> None:
    with GROQ_USAGE_LOG.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def groq_check_and_update_usage(required_tokens: int) -> bool:
    usage = load_groq_usage()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    stats = usage.get(today, {"calls": 0, "tokens": 0})
    if stats["calls"] >= GROQ_DAILY_CALL_LIMIT:
        print(f"Groq daily call limit of {GROQ_DAILY_CALL_LIMIT} reached for {today}.")
        return False
    stats["calls"] += 1
    stats["tokens"] += required_tokens
    usage[today] = stats
    save_groq_usage(usage)
    print(f"Groq usage today — calls: {stats['calls']}/{GROQ_DAILY_CALL_LIMIT}, tokens logged: {stats['tokens']}")
    return True


def groq_call_with_retry(prompt: str, max_retries: int = 3, base_delay: float = 6.0, max_delay: float = 30.0) -> str:
    if not groq_client:
        raise RuntimeError("Groq API key not configured; cannot use Groq fallback.")

    for attempt in range(max_retries + 1):
        try:
            estimated_tokens = estimate_tokens(prompt)
            if not groq_check_and_update_usage(estimated_tokens):
                raise RuntimeError("Groq daily call limit reached.")

            messages = [
                {
                    "role": "system",
                    "content": "You are a meticulous assistant. Follow the user's instructions exactly.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ]
            response = groq_client.chat.completions.create(
                model="groq/compound",
                messages=messages,
                temperature=0.4,
                max_completion_tokens=2048,
                top_p=1,
            )
            content = response.choices[0].message.content if response.choices else ""
            if not content:
                raise ValueError("Groq returned empty response")
            time.sleep(max(10.0, DEFAULT_DELAY_AFTER_REQUEST))
            return content
        except Exception as e:
            if attempt == max_retries:
                raise
            delay = min(base_delay * (2 ** attempt), max_delay)
            print(f"Groq attempt {attempt + 1} failed: {e}. Retrying in {delay:.1f} seconds...")
            time.sleep(delay)


def call_llm_with_failover(prompt: str, response_mime_type: Optional[str] = None) -> str:
    """
    Attempt to generate content using the currently active provider.
    If it fails, rotate through available providers (Gemini -> Groq -> Gemini ...).
    """
    if not PROVIDER_NAMES:
        raise RuntimeError("No LLM providers available.")

    global ACTIVE_PROVIDER_INDEX
    provider_rotations = 0
    last_error: Exception | None = None

    while provider_rotations <= len(PROVIDER_NAMES):
        provider = PROVIDER_NAMES[ACTIVE_PROVIDER_INDEX]
        try:
            if provider == "gemini":
                result = gemini_call_with_retry(prompt, response_mime_type=response_mime_type)
            elif provider == "groq":
                # Groq always returns text; response mime ignored
                result = groq_call_with_retry(prompt)
            else:
                raise RuntimeError(f"Unknown provider '{provider}'")

            PROVIDER_FAILURE_COUNTS[provider] = 0
            return result
        except Exception as exc:
            last_error = exc
            PROVIDER_FAILURE_COUNTS[provider] = PROVIDER_FAILURE_COUNTS.get(provider, 0) + 1
            print(f"{provider.upper()} provider failed ({PROVIDER_FAILURE_COUNTS[provider]} consecutive). Error: {exc}")
            if PROVIDER_FAILURE_COUNTS[provider] >= PROVIDER_FAIL_THRESHOLD:
                PROVIDER_FAILURE_COUNTS[provider] = 0
                ACTIVE_PROVIDER_INDEX = (ACTIVE_PROVIDER_INDEX + 1) % len(PROVIDER_NAMES)
                provider_rotations += 1
                print(f"Switching to provider '{PROVIDER_NAMES[ACTIVE_PROVIDER_INDEX]}' after repeated failures.")
            else:
                print(f"Retrying provider '{provider}' (failure count below threshold).")
            time.sleep(5)

    raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")

def gemini_call_with_retry(prompt, response_mime_type=None, max_retries=5, base_delay=6.0, max_delay=30.0):
    """
    Calls the model with retries using exponential backoff.
    
    Args:
        prompt (str): The prompt to send to the model.
        max_retries (int): Maximum number of retries.
        base_delay (float): Initial delay between retries in seconds.
        max_delay (float): Maximum delay between retries in seconds.
    
    Returns:
        response: The model response.
    
    Raises:
        Exception: If all retries fail.
    """
    global CURRENT_MODEL, client, CURRENT_API_KEY_INDEX
    for attempt in range(max_retries + 1):
        try:
            model_name = choose_model(CURRENT_MODEL)
            print(f"Using API key #{CURRENT_API_KEY_INDEX + 1}")
            print(f"Using model: {model_name}")
            config = {
                "tools": [{"google_search": {}}],
            }

            # if response_mime_type and response_mime_type != "application/json":
            #     config["response_mime_type"] = response_mime_type
            
            request_kwargs = {
                "model": model_name,
                "contents": prompt,
                "config": config,
            }
            response = client.models.generate_content(**request_kwargs)
            record_request(model_name)
            CURRENT_MODEL = model_name
            FAILURE_COUNTS[model_name] = 0
            API_KEY_FAILURE_COUNTS[CURRENT_API_KEY_INDEX] = 0
            time.sleep(DEFAULT_DELAY_AFTER_REQUEST)
            result = response.text if hasattr(response, 'text') and response.text else ""
            if not result:
                raise ValueError("Model returned empty response")
            return result
        except Exception as e:
            FAILURE_COUNTS[model_name] = FAILURE_COUNTS.get(model_name, 0) + 1
            API_KEY_FAILURE_COUNTS[CURRENT_API_KEY_INDEX] = (
                API_KEY_FAILURE_COUNTS[CURRENT_API_KEY_INDEX] + 1
            )
            if FAILURE_COUNTS[model_name] > FAIL_THRESHOLD:
                other_model = PRO_MODEL if model_name == FLASH_MODEL else FLASH_MODEL
                print(f"Encountered {FAILURE_COUNTS[model_name]} consecutive failures on {model_name}. Switching preference to {other_model}.")
                CURRENT_MODEL = other_model
                FAILURE_COUNTS[model_name] = 0
                FAILURE_COUNTS[other_model] = 0

            if API_KEY_FAILURE_COUNTS[CURRENT_API_KEY_INDEX] > API_KEY_FAIL_THRESHOLD:
                if len(AVAILABLE_API_KEYS) > 1:
                    print(
                        f"Encountered {API_KEY_FAILURE_COUNTS[CURRENT_API_KEY_INDEX]} consecutive failures on API key #{CURRENT_API_KEY_INDEX + 1}. "
                        "Switching to the next API key."
                    )
                    API_KEY_FAILURE_COUNTS[CURRENT_API_KEY_INDEX] = 0
                    switch_api_key()
                    continue
                else:
                    print("Only one API key configured; cannot rotate keys despite failures.")

            if attempt == max_retries:
                raise  # all retries failed
            delay = min(base_delay * (2 ** attempt), max_delay)
            wait_time = max(DEFAULT_DELAY_AFTER_REQUEST, delay)
            print(f"Attempt {attempt + 1} failed: {e}. Retrying in {wait_time:.1f} seconds...")
            time.sleep(wait_time)

def extract_json_string(text: str) -> str:
    """Extract a JSON string from LLM text which may include markdown fences."""
    if not text:
        return "{}"
    
    text = text.strip()
    
    # 1) Try fenced code block with json
    fenced = re.findall(r"```json\s*([\s\S]*?)\s*```", text, flags=re.IGNORECASE)
    if fenced:
        candidate = fenced[0].strip()
        # Validate it's actually JSON
        try:
            json.loads(candidate)
            return candidate
        except (json.JSONDecodeError, ValueError):
            pass

    # 2) Try any fenced block without language
    fenced_any = re.findall(r"```\s*([\s\S]*?)\s*```", text)
    for block in fenced_any:
        block_stripped = block.strip()
        if block_stripped.startswith("{") or block_stripped.startswith("["):
            try:
                json.loads(block_stripped)
                return block_stripped
            except (json.JSONDecodeError, ValueError):
                continue

    # 3) Heuristic: try parsing from each '{' or '['
    for start_char in ["{", "["]:
        brace_indices = [m.start() for m in re.finditer(re.escape(start_char), text)]
        for start in brace_indices:
            snippet = text[start:]
            # Find matching closing brace/bracket
            depth = 0
            end = -1
            for i, char in enumerate(snippet):
                if char in ["{", "["]:
                    depth += 1
                elif char in ["}", "]"]:
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            
            if end > 0:
                candidate = snippet[:end].strip()
                if candidate:
                    try:
                        json.loads(candidate)
                        return candidate
                    except (json.JSONDecodeError, ValueError):
                        continue

    # 4) Try parsing the whole text as JSON
    try:
        json.loads(text)
        return text
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: return empty JSON object
    return "{}"


def _url_is_reachable(url: str, session: requests.Session, timeout: float = 5.0) -> bool:
    """Return True only if the URL responds with a successful status."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    try:
        response = session.head(url, allow_redirects=True, timeout=timeout)
        if response.status_code >= 400:
            response = session.get(url, allow_redirects=True, timeout=timeout)
        return response.status_code < 400
    except requests.RequestException:
        return False


def validate_reference_urls(ref_urls: list) -> list[str]:
    """
    Validate reference URLs by checking they are reachable.
    Returns only the URLs that pass validation.
    """
    if not isinstance(ref_urls, list) or not ref_urls:
        return []

    session = requests.Session()
    validated: list[str] = []

    for entry in ref_urls:
        if isinstance(entry, str):
            candidate = entry.strip()
        elif isinstance(entry, dict):
            candidate = str(entry.get("url", "")).strip()
        else:
            continue

        if candidate and _url_is_reachable(candidate, session):
            validated.append(candidate)

    return validated

def get_children_for_group(json_file, group_name):
    """
    Given a second_level_tree.json and a group name,
    return all nested children as a formatted string.
    If the group has no children, return a message indicating that.
    """

    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    if group_name not in data:
        available = ', '.join(data.keys())
        return f"Group '{group_name}' not found in {json_file}\nAvailable groups: {available}"

    tree = data[group_name]

    if not tree:
        return f"{group_name} has no children"

    def build_children_string(tree, level=0):
        result = ""
        indent = "  " * level
        if isinstance(tree, dict):
            for key, value in tree.items():
                result += f"{indent}- {key}\n"
                result += build_children_string(value, level + 1)
        elif isinstance(tree, list):
            for item in tree:
                if isinstance(item, dict):
                    result += build_children_string(item, level)
                else:
                    result += f"{indent}- {item}\n"
        return result

    children_str = f"\nChildren of '{group_name}':\n"
    children_str += build_children_string(tree)
    return children_str



def load_list_from_file(path: Path) -> list[str]:
    if not path.exists():
        raise SystemExit(f"Required file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def load_metadata_assets(path: Path) -> list[dict]:
    if not path.exists():
        raise SystemExit(f"Metadata file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        assets = json.load(f)

    if not isinstance(assets, list):
        raise SystemExit("Expected metadata file to contain a list of assets' data.")

    return assets


def build_output_filename(index: int) -> str:
    """Use the legacy asset naming convention."""
    return f"asset_{index}.json"


def estimate_tokens(text: str) -> int:
    """
    Rough token estimate without external API calls.
    Approximation: 1 token ≈ 4 characters.
    """
    if not text:
        return 0
    return max(1, len(text) // 4)


def normalize_tech_group_choice(raw_choice: str) -> str:
    if raw_choice is None:
        return ""

    choice = raw_choice.strip().strip('"').strip()
    if not choice:
        return ""

    first_line = choice.splitlines()[0].strip()
    if ":" in first_line:
        first_line = first_line.split(":", 1)[-1].strip()

    if first_line.lower() in {"none", "null"}:
        return ""

    return first_line


def find_closest_tech_group(choice: str, groups: list[str], cutoff: float = 0.7) -> str:
    """
    Return the closest matching tech group using fuzzy matching if an exact match does not exist.
    """
    if not choice:
        return ""
    matches = get_close_matches(choice, groups, n=1, cutoff=cutoff)
    return matches[0] if matches else ""


TECH_TYPES = load_list_from_file(TECH_TYPES_FILE)
TECH_GROUPS = load_list_from_file(TECH_GROUPS_FILE)

# Load failed asset data
data = load_metadata_assets(METDATA_FILE)


for i, metadata in enumerate(data, start=1):

    output_filename = build_output_filename(i)
    output_path = OUTPUT_DIR / output_filename

    if output_path.exists():
        print(f"Skipping Asset #{i} — {output_filename} already exists.")
        continue

    try:
        metadata = json.dumps(metadata, indent=2, ensure_ascii=False)
    except (TypeError, ValueError):
        metadata = str(metadata)

    TECH_GROUPS_JSON = json.dumps(TECH_GROUPS, indent=2)
    TECH_TYPES_JSON = json.dumps(TECH_TYPES, indent=2)

    prompt_one = f"""

        You are classifying a hardware asset into exactly ONE tech group.

        ASSET DATA:
        {metadata}
        NOTE:
        Information inside this JSON may be incomplete, inaccurate, or wrong (provided type/manufacturer/model or other information could be wrong/invalid) 

        INSTRUCTIONS:
        1. Perform a web search to identify what this asset is.
        2. Select the SINGLE MOST ACCURATE tech group from the list below (information provided in this json could be wrong).
        3. You MUST respond with ONLY the name of a tech group from the list. 
        4. DO NOT add explanations, reasoning, extra words, sentences, markdown, quotes, or commentary, just return the name of selected tech group
        5. If unsure, pick the closest match from the list.

        VALID TECH GROUPS:
        {TECH_GROUPS_JSON}

        OUTPUT FORMAT:
        "tech_group_name"

    """


    estimated_tokens_prompt_one = estimate_tokens(prompt_one)
    print(f"Estimated tokens for prompt_one (Asset #{i}): {estimated_tokens_prompt_one}")

    tech_group_raw = call_llm_with_failover(prompt_one, response_mime_type="text/plain")
    tech_group_result = normalize_tech_group_choice(tech_group_raw)

    if not tech_group_result:
        print("No tech group returned for this asset; skipping.")
        continue

    if tech_group_result not in TECH_GROUPS:
        matches = [group for group in TECH_GROUPS if group.lower() == tech_group_result.lower()]
        if matches:
            tech_group_result = matches[0]
        else:
            closest_match = find_closest_tech_group(tech_group_result, TECH_GROUPS)
            if closest_match:
                print(f"Tech group '{tech_group_result}' not found. Using closest match '{closest_match}'.")
                tech_group_result = closest_match
            else:
                print(f"Model returned an unknown tech group '{tech_group_result}'. Skipping asset.")
                continue

    print("Gemini chose this as the tech group: ", tech_group_result)
    print()
    tech_group_json = re.sub(r'\W+', '_', tech_group_result) + ".json"

    print("Corresponding JSON file: ", tech_group_json)
    print()

    children_output = get_children_for_group(SECOND_LEVEL_TREE_FILE, tech_group_result)
    print(children_output)

    json_file_path = TECHGROUP_JSON_DIR / tech_group_json

    with json_file_path.open("r", encoding="utf-8") as f:
        schema_data = json.load(f)

    cleaned_schema = json.dumps(schema_data, indent=2)

    prompt_two = f"""
            
        You are completing a JSON structure for this hardware asset:

        ASSET DATA:
        {metadata}

        JSON SCHEMA TO FILL:
        {cleaned_schema}

        TECH TYPE OPTIONS (choose exactly one):
        {TECH_TYPES_JSON}

        VALID TECH GROUP OPTIONS (choose exactly one):
        {children_output}

        INSTRUCTIONS:
        1. Perform a web search to identify accurate information about this asset.
        2. Fill ALL fields in the JSON schema concisely.
        3. If a field cannot be determined, write "Not found".
        4. For "tech_type", select ONLY from the provided list.
        5. For "tech_group", select ONLY from the provided list, pick the one that most specifically describes the asset.
        6. Add an extra field named "reference_urls": a list containing valid URLs;
            - Use ONLY URLs that appear directly within the Google Search snippets obtained through the google_search tool.
            - Do NOT invent URLs.
            - Do NOT rewrite URLs.
            - Do NOT fabricate product pages.
        7. Return ONLY a valid JSON object.
        8. DO NOT write any sentences, explanations, descriptions, markdown, or text outside the JSON.

    """

    estimated_tokens_prompt_two = estimate_tokens(prompt_two)
    print(f"Estimated tokens for prompt_two (Asset #{i}): {estimated_tokens_prompt_two}")

    json_response_text = call_llm_with_failover(prompt_two, response_mime_type="application/json")
    print(json_response_text)
    # Debugging print statements
    print(f"\n--- Result for Asset #{i} ---\n{json_response_text}\n")
    print("=" * 100)

    # Extract and validate JSON
    if json_response_text:
        extracted_json = extract_json_string(json_response_text)
        # Validate JSON is parseable
        try:
            parsed = json.loads(extracted_json)
            if isinstance(parsed, dict):
                parsed["reference_urls"] = validate_reference_urls(parsed.get("reference_urls", []))
                output_text = json.dumps(parsed, indent=2, ensure_ascii=False)
            else:
                # Keep original structure if it's not a dict
                output_text = extracted_json
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Warning: Extracted JSON is invalid: {e}")
            print("Falling back to raw response")
            output_text = json_response_text.strip() if json_response_text.strip() else "{}"
    else:
        output_text = "{}"
    
    with output_path.open("w", encoding="utf-8") as f:
        f.write(output_text)
        if not output_text.endswith("\n"):
            f.write("\n")

    print(f"Saved enriched asset to {output_path}")


    