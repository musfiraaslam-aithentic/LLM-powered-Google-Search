import os
import json
import time
from typing import Dict, Any, Optional
from google import genai
from dotenv import load_dotenv

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    raise SystemExit("GOOGLE_API_KEY is not set in the environment. Please set it in your .env file.")

client = genai.Client()

# Directory paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
QUERIES_FILE = os.path.join(SCRIPT_DIR, "json_query.json")
CATEGORIES_DIR = os.path.join(SCRIPT_DIR, "categories")
JSON_RESULTS_DIR = os.path.join(SCRIPT_DIR, "json_results")

# Ensure directories exist
os.makedirs(JSON_RESULTS_DIR, exist_ok=True)

def load_json_schema(category_type: str) -> Dict[str, Any]:
    """Load the appropriate JSON schema based on product type."""
    # Convert type to lowercase and replace spaces with underscores
    normalized_type = category_type.lower().replace(" ", "_")
    
    # Create schema filename
    schema_file = f"{normalized_type}.json"
    schema_path = os.path.join(CATEGORIES_DIR, schema_file)
    
    if not os.path.exists(schema_path):
        # Try common mappings for types that might have different names
        if normalized_type in ["monitor", "display"]:
            schema_file = "display.json"
        elif normalized_type == "cloud_instance":
            schema_file = "cloud_instance.json"
        elif normalized_type == "docking_station":
            schema_file = "docking_station.json"
        elif normalized_type == "iot_device":
            schema_file = "iot_device.json"
        elif normalized_type in ["laptop", "notebook"]:
            schema_file = "laptop.json"
        
        schema_path = os.path.join(CATEGORIES_DIR, schema_file)
    
    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    
    with open(schema_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def create_search_query(manufacturer: str, model: str, serial_number: str, category_type: str) -> str:
    """Create a search query string."""
    query_parts = [manufacturer, model]
    if serial_number and serial_number.lower() not in ["unknown", "null"]:
        query_parts.append(f"serial {serial_number}")
    
    return " ".join(query_parts)

def create_prompt(query: str, json_schema: Dict[str, Any]) -> str:
    """Create the full prompt for Gemini."""
    schema_str = json.dumps(json_schema, indent=2)
    
    prompt = f"""Search for {query}

    Provide the following information and fill this JSON structure:

    {schema_str}

    Instructions:
    - Fill in all the fields with accurate information found from your search
    - If information is not available, use "Not found" or "Unknown"
    - Ensure all data is accurate and from reliable sources
    Return the response in the exact JSON format provided above."""
    
    return prompt

def safe_filename(manufacturer: str, model: str) -> str:
    """Create a safe filename from manufacturer and model."""
    import re
    # Clean manufacturer and model for filename
    clean_manufacturer = re.sub(r'[\\/:"*?<>|]+', "_", manufacturer)
    clean_model = re.sub(r'[\\/:"*?<>|]+', "_", model)
    return f"{clean_manufacturer}_{clean_model}.json"

def process_products(item: Dict[str, Any], model: str = "gemini-2.5-flash") -> None:
    """Process a single item and save the result."""
    manufacturer = item.get("manufacturer", "")
    model_name = item.get("model", "")
    serial_number = item.get("serial_number", "")
    category_type = item.get("type", "")
    
    print(f"Processing: {manufacturer} {model_name} ({category_type})")
    
    # Load appropriate JSON schema
    try:
        json_schema = load_json_schema(category_type)
    except Exception as e:
        print(f"Error loading schema for {category_type}: {e}")
        return
    
    # Create search query and prompt
    search_query = create_search_query(manufacturer, model_name, serial_number, category_type)
    prompt = create_prompt(search_query, json_schema)
    
    # Call Gemini API
    try:
        start_time = time.time()
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config={"tools": [{"google_search": {}}]},
        )
        response_time = time.time() - start_time
        
        # Extract JSON from response
        raw_text = response.text if hasattr(response, "text") else str(response)
        json_str = extract_json_string(raw_text)
        
        try:
            json_obj = json.loads(json_str)
        except Exception as e:
            print(f"Failed to parse JSON for {manufacturer} {model_name}: {e}")
            print(f"Raw response: {raw_text[:200]}...")
            return
        
        # Save to file
        filename = safe_filename(manufacturer, model_name)
        output_path = os.path.join(JSON_RESULTS_DIR, filename)
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(json_obj, f, ensure_ascii=False, indent=2)
        
        print(f"Saved to {output_path} ({response_time:.2f}s)")
        
    except Exception as e:
        print(f"Error processing {manufacturer} {model_name}: {e}")

def extract_json_string(text: str) -> str:
    """Extract a JSON string from LLM text which may include markdown fences."""
    import re
    
    # 1) Try fenced code block with json
    fenced = re.findall(r"```json\s*([\s\S]*?)\s*```", text, flags=re.IGNORECASE)
    if fenced:
        candidate = fenced[0].strip()
        return candidate

    # 2) Try any fenced block without language
    fenced_any = re.findall(r"```\s*([\s\S]*?)\s*```", text)
    for block in fenced_any:
        block_stripped = block.strip()
        if block_stripped.startswith("{"):
            return block_stripped

    # 3) Heuristic: try parsing from each '{'
    brace_indices = [m.start() for m in re.finditer(r"\{", text)]
    for start in brace_indices:
        snippet = text[start:]
        close_indices = [m.end() for m in re.finditer(r"\}", snippet)]
        for end in reversed(close_indices):
            candidate = snippet[:end]
            candidate_stripped = candidate.strip()
            if candidate_stripped:
                try:
                    json.loads(candidate_stripped)
                    return candidate_stripped
                except Exception:
                    continue

    # Fallback: return the whole text
    return text.strip()

def main():
    """Main function to process all queries."""
    # Load queries
    if not os.path.exists(QUERIES_FILE):
        print(f"Queries file not found: {QUERIES_FILE}")
        return
    
    with open(QUERIES_FILE, 'r', encoding='utf-8') as f:
        items = json.load(f)
    
    print(f"Processing {len(items)} items...")
    
    for i, item in enumerate(items, 1):
        print(f"\n--- Item {i}/{len(items)} ---")
        process_products(item)
        
        # Add a small delay between requests to avoid rate limiting
        if i < len(items):
            time.sleep(2)
    
    print(f"\nCompleted processing {len(items)} items.")
    print(f"Results saved to: {JSON_RESULTS_DIR}")

if __name__ == "__main__":
    main()
