import json
import re
import os
import time
from google import genai
from google.genai import types
from typing import Dict
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    raise SystemExit("GOOGLE_API_KEY not set in environment!")

# Initialize client
client = genai.Client()

# Model for just product_features
class TechGroupFeatures(BaseModel):
    product_features: Dict[str, str]

# Full asset model
class AssetInfo(BaseModel):
    brand: str
    brand_country: str
    brand_domain: str
    tech_type: str
    tech_group: str
    product_id: str
    product_desc: str
    product_features: Dict[str, str]

# Configure generation without grounding tool, JSON output only
test_config = types.GenerateContentConfig(
    response_mime_type='application/json'
)

# Folder to save JSON files
output_folder = "techgroup_jsons"
os.makedirs(output_folder, exist_ok=True)

# Read tech groups from file
with open("second_level_techgroups.txt", "r", encoding="utf-8") as f:
    tech_groups = [line.strip() for line in f if line.strip()]

# Free tier daily limit
DAILY_LIMIT = 250
request_count = 0

for tech_group in tech_groups:
    # Stop if daily limit is reached
    if request_count >= DAILY_LIMIT:
        print(f"Daily request limit reached ({DAILY_LIMIT}). Stopping script.")
        break

    # Sanitize filename
    sanitized_name = re.sub(r'\W+', '_', tech_group.strip())
    filename = os.path.join(output_folder, f"{sanitized_name}.json")

    # Skip if file already exists
    if os.path.exists(filename):
        print(f"Skipping '{tech_group}' (file already exists).")
        continue

    print(f"Generating JSON for '{tech_group}'...")

    prompt = f"""
    This is a tech group: {tech_group}

    Return a JSON object with a single field `product_features`.
    `product_features` should be a dictionary (key-value pairs) where
    keys are feature names relevant to this tech group, and values are empty strings.

    Do NOT provide any actual specs; just leave the values empty.
    For example:
    {{
      "product_features": {{
        "Screen Size": "",
        "Resolution": ""
      }}
    }}
    """

    # Retry loop for 503 errors
    max_retries = 3
    retries = 0
    while retries <= max_retries:
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=(prompt),
                config=test_config,
            )

            request_count += 1  # Increment request counter
            print(f"Requests used: {request_count}/{DAILY_LIMIT}")

            response_data = json.loads(response.text)
            features_dict = response_data.get("product_features", {})

            # Build empty AssetInfo
            asset_info = AssetInfo(
                brand="",
                brand_country="",
                brand_domain="",
                tech_type="",
                tech_group=tech_group,
                product_id="",
                product_desc="",
                product_features=features_dict
            )

            # Save to file
            with open(filename, "w", encoding="utf-8") as f:
                f.write(asset_info.model_dump_json(indent=2))

            print(f"Saved JSON for '{tech_group}' -> {filename}")
            break  # exit retry loop on success

        except json.JSONDecodeError:
            print(f"Failed to parse JSON for '{tech_group}':")
            print(response.text)
            break  # no point retrying invalid JSON
        except Exception as e:
            if "503 UNAVAILABLE" in str(e):
                retries += 1
                wait_time = 2
                print(f"503 error for '{tech_group}', retrying in {wait_time} seconds... ({retries}/{max_retries})")
                time.sleep(wait_time)
            else:
                print(f"Error creating AssetInfo model for '{tech_group}': {e}")
                break

    # Delay 6 seconds between requests
    time.sleep(6)
