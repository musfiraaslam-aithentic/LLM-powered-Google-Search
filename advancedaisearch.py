import json
from pathlib import Path
from google import genai
from google.genai import types
import os
from dotenv import load_dotenv 
import time
import re
from difflib import get_close_matches

# Load environment variables
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

BASE_DIR = Path(__file__).resolve().parent
TECH_GROUPS_FILE = BASE_DIR / "tech_groups.txt"
TECH_TYPES_FILE = BASE_DIR / "tech_types.txt"
SECOND_LEVEL_TREE_FILE = BASE_DIR / "second_level_tree.json"
TECHGROUP_JSON_DIR = BASE_DIR / "techgroup_jsons"
METDATA_FILE = BASE_DIR / "metadata.json"
OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

if not GOOGLE_API_KEY:
    raise SystemExit("GOOGLE_API_KEY not set in environment!")

# Initialize client
client = genai.Client()

# Rate limits
requests_per_minute = 10
tokens_per_minute = 250000
requests_per_day = 250
ideal_tokens_per_request = tokens_per_minute / requests_per_minute

# Enable Google Search tool
grounding_tool = types.Tool(
    google_search=types.GoogleSearch()
)

# Configure generation with the grounding tool
config = types.GenerateContentConfig(
    tools=[grounding_tool]
)

def model_call_with_retry(prompt, max_retries=5, base_delay=6.0, max_delay=30.0):
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
    for attempt in range(max_retries + 1):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-pro",
                contents=prompt,
                config=config,
            )
        except Exception as e:
            if attempt == max_retries:
                raise  # all retries failed
            delay = min(base_delay * (2 ** attempt), max_delay)
            wait_time = max(10.0, delay)
            print(f"Attempt {attempt + 1} failed: {e}. Retrying in {wait_time:.1f} seconds...")
            time.sleep(wait_time)
        else:
            time.sleep(15)
            return response

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

def add_citations_at_end(response):
    text = response.text
    supports = response.candidates[0].grounding_metadata.grounding_supports
    chunks = response.candidates[0].grounding_metadata.grounding_chunks
    
    citation_dict = {}
    for support in supports:
        for i in support.grounding_chunk_indices:
            if i < len(chunks):
                uri = chunks[i].web.uri
                title = getattr(chunks[i].web, 'title', uri)
                citation_dict[i] = (uri, title)
    
    if citation_dict:
        citations_text = "\n\nReference Urls:\n"
        for idx, (uri, title) in enumerate(citation_dict.values(), start=1):
            citations_text += f"[{idx}] {title} - {uri}\n"
        text += citations_text
    
    return text



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


def extract_json_payload(text: str) -> str | None:
    if not text:
        return None
    code_block_pattern = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
    match = code_block_pattern.search(text)
    if match:
        return match.group(1).strip()
    return None


def build_output_filename(index: int, metadata: dict, tech_group: str) -> str:
    model = ""
    manufacturer = ""

    if isinstance(metadata, dict):
        hardware = metadata.get("hardware_data") if isinstance(metadata.get("hardware_data"), dict) else {}
        model = hardware.get("model") 
        manufacturer = hardware.get("manufacturer") 

    parts = [f"asset_{index:04d}"]
    if manufacturer:
        parts.append(manufacturer)
    if model:
        parts.append(model)
    if tech_group:
        parts.append(tech_group)

    raw_name = "_".join(parts)
    safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", raw_name)
    return f"{safe_name}.json"


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

    try:
        metadata = json.dumps(metadata, indent=2, ensure_ascii=False)
    except (TypeError, ValueError):
        metadata = str(metadata)

    TECH_GROUPS_JSON = json.dumps(TECH_GROUPS, indent=2)
    TECH_TYPES_JSON = json.dumps(TECH_TYPES, indent=2)

    prompt = f"""

        You are classifying a hardware asset into exactly ONE tech group.

        ASSET DATA:
        {metadata}
        NOTE:
        Information inside this JSON may be incomplete, inaccurate, or wrong. 

        INSTRUCTIONS:
        1. Perform a web search to identify what this asset is.
        2. Select the SINGLE MOST ACCURATE tech group from the list below (information provided in this json could be wrong).
        3. You MUST respond with ONLY the name of a tech group from the list. 
        4. DO NOT add explanations, reasoning, extra words, sentences, markdown, quotes, or commentary.
        5. If unsure, pick the closest match from the list.

        VALID TECH GROUPS:
        {TECH_GROUPS_JSON}

        OUTPUT FORMAT:
        "tech_group_name"

    """

    #print("This is the prompt\n", prompt)
    #print()

    # There is no charge or quota restriction for using the CountTokens API. 
    # The maximum quota for the CountTokens API is 3000 requests per minute.
    # https://docs.cloud.google.com/vertex-ai/generative-ai/docs/multimodal/get-token-count
    
    try:
        token_info = client.models.count_tokens(
            model="gemini-2.5-flash",  
            contents=prompt
        )
    finally:
        time.sleep(15)
    
    total_tokens = token_info.total_tokens  

    if total_tokens < ideal_tokens_per_request:
        response = model_call_with_retry(prompt)
        
        tech_group_raw = getattr(response, "text", "")
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

        promptTwo = f"""
                
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
            2. Fill ALL fields in concisely the JSON schema.
            3. If a field cannot be determined, write "Not found".
            4. For "tech_type", select ONLY from the provided list.
            5. For "tech_group", select ONLY from the provided second-level list.
            6. Return ONLY a valid JSON object.
            7. DO NOT write any sentences, explanations, descriptions, markdown, or text outside the JSON.

        """

        response = model_call_with_retry(promptTwo)
        #final_result = add_citations_at_end(response)

        # Debugging print statements
        print(f"\n--- Result for Asset #{i} ---\n{response}\n")
        print(f"Total Tokens in Prompt: {total_tokens}/{ideal_tokens_per_request}")
        print("=" * 100)

        json_payload = extract_json_payload(response.text)
        output_text = json_payload if json_payload else response.text
        output_filename = build_output_filename(i, metadata, tech_group_result)
        output_path = OUTPUT_DIR / output_filename
        with output_path.open("w", encoding="utf-8") as f:
            f.write(output_text)
            if not output_text.endswith("\n"):
                f.write("\n")

        print(f"Saved enriched asset to {output_path}")

    else:
        print("Prompt is too large skipping asset.")
        continue