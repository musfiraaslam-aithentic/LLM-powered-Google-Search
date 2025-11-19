import json
import os
import re
from groq import Groq
import time
from dotenv import load_dotenv
from pathlib import Path
load_dotenv()


BASE_DIR = Path(__file__).resolve().parent

TECH_GROUPS_FILE = BASE_DIR.joinpath("tech_groups.txt")
TECH_TYPES_FILE = BASE_DIR.joinpath("tech_types.txt")


METDATA_FILE = BASE_DIR.joinpath("metadata.json")
OUTPUT_DIR = BASE_DIR.joinpath("groq")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def countdown(minutes):
    total_seconds = minutes * 60
    while total_seconds:
        mins, secs = divmod(total_seconds, 60)
        timer = f"Cooldown Period {mins:02d}:{secs:02d}"
        print(timer, end='\r')  
        time.sleep(1)
        total_seconds -= 1
    print()  

def reference_urls(tool_results):
    print("\nReference Urls:\n")

    if not tool_results or not tool_results.results:
        print("No reference URLs found.\n")
        return

    # Sort by highest -> lowest score
    results_sorted = sorted(
        tool_results.results,
        key=lambda r: r.score,
        reverse=True
    )

    # Print in neat JSON style
    for r in results_sorted:
        print("{")
        print(f'  "title": "{r.title}",')
        print(f'  "url": "{r.url}",')
        print(f'  "score": {r.score}')
        print("}\n")

def load_list_from_file(path):
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

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
        return f"❌ Group '{group_name}' not found in {json_file}\nAvailable groups: {available}"

    tree = data[group_name]

    # Check if the tree is empty
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

    children_str = f"\n📂 Children of '{group_name}':\n"
    children_str += build_children_string(tree)
    return children_str


TECH_TYPES = json.dumps(load_list_from_file(TECH_TYPES_FILE), indent=2)
TECH_GROUPS = json.dumps(load_list_from_file(TECH_GROUPS_FILE), indent=2)
# Load your asset data

with METDATA_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)


def extract_json_block(text: str) -> tuple[str | None, str]:
    """Return (json_string, text_without_json_block)."""
    if not text:
        return None, ""

    json_match = re.search(r"```json\s*([\s\S]*?)```", text, re.IGNORECASE)
    if not json_match:
        json_match = re.search(r"```\s*([\s\S]*?)```", text)

    if json_match:
        json_str = json_match.group(1).strip()
        stripped_text = text[:json_match.start()] + text[json_match.end():]
        return json_str, stripped_text.strip()

    # Fallback: try to detect first {...} or [...]
    brace_match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
    if brace_match:
        json_str = brace_match.group(1).strip()
        stripped_text = text[:brace_match.start()] + text[brace_match.end():]
        return json_str, stripped_text.strip()

    return None, text

# Initialize Groq client
client = Groq(
    api_key=os.getenv("GROQ_API_KEY"),
    default_headers={
        "Groq-Model-Version": "latest",
    }
)

instructions = """
   
    You role is to strictly identify the tech group.

    1. Output ONLY the final answer.
    2. DO NOT include reasoning.
    3. DO NOT include explanations.
    4. DO NOT include markdown.
    5. DO NOT repeat the question.
    6. If you include anything except the exact required answer, your output is INVALID.

    You must follow these rules and your response should be less than 5 words anymore your output is INVALID

    You should not add headers like **Chosen Tech Group:** Docking Cradles it should only return it simple like Docking Cradles

    Things to consider in response:
        1. Sometimes in the metadata it might mention docking but the device maybe something else.

        For example, the passed asset data has 

        "TYPE": "docking station",
        "MODEL": "Inspiron 7472",
        "MANUFACTURER": "Dell",

        Now based on the data this is actually a laptop Inspiron 7472

"""

for i, metadata in enumerate(data, start=1):
    try:
        metadata_text = json.dumps(metadata, indent=2, ensure_ascii=False)
    except (TypeError, ValueError):
        metadata_text = str(metadata)

    prompt = f"""
        The data provided is of an asset which we were unable to match or identify.

        This is the data we received:
            Metadata: {metadata_text}

        From the following list of tech groups, choose the **one group** that best represents the asset.
        - Return **exactly one value** from the list.
        - If there is not enough information, return **null**.
        - Return **only the chosen value**, no explanations or extra text.

        {TECH_GROUPS}
    """

    # Send prompt to Groq
    completion = client.chat.completions.create(
        model="groq/compound",
        messages=[
            {"role": "system", "content": instructions},
            {"role": "user", "content": prompt}
        ],
        temperature=1,
        max_completion_tokens=3,
        top_p=1,
        stream=False,
        stop=None,
    )

    # Get the response text
    response = completion.choices[0].message.content
    tech_group_result = response

    print(f"Groq chose this as the tech group for asset #{i}: {tech_group_result}")
    print()

    tech_group_json = re.sub(r'\W+', '_', tech_group_result) + ".json"

    print("Corresponding JSON file: ", tech_group_json)
    print()

    children_output = get_children_for_group("second_level_tree.json", tech_group_result)
    print(children_output)

    json_folder = "techgroup_jsons"
    json_file_path = os.path.join(json_folder, tech_group_json)

    with open(json_file_path, "r", encoding="utf-8") as f:
        schema_data = json.load(f)

    cleaned_schema = json.dumps(schema_data, indent=2)

    promptTwo = f"""
        
        The data provided is of an asset which we were unable to match or identify.
        
        This is the data we received:

            Metadata: {metadata_text}

        Using this data help to find the exact model. 
        
        If you are unable to find the exact model find the closest results.

        Return these pieces of data

        Brand/Manufacturer/Vendor: (e.g. Apple or ASUS)
        Brand Country: 
        Brand Domain: (e.g. https://www.asus.com/ or https://www.apple.com/)
        Tech Type: Use the most appropriate value from; {children_output}
        
        Product SKU/ID: 
        Product Description: 
        Product Features: Only list 5 features (e.g., RAM, CPU, Display, Refresh Rate, etc.)

        Make sure to fill this json file and enrich the data

        {cleaned_schema}
    """
    # WAIT 1 minute BEFORE SENDING NEXT PROMPT
    countdown(1)

    # Send prompt to Groq
    completion = client.chat.completions.create(
        model="groq/compound",
        messages=[
          {
            "role": "user",
            "content": promptTwo
          }
        ],
        temperature=1,
        max_completion_tokens=1024,
        top_p=1,
        stream=False,
        stop=None,
        compound_custom={"tools":{"enabled_tools":["web_search","visit_website"]}}
    )

    # Get the response text
    final_result = completion.choices[0].message.content

    tools_used = None
    if completion.choices[0].message.executed_tools: 
        tools_used = completion.choices[0].message.executed_tools[0].search_results

    print()
    print(f"\n--- Final Result for Asset #{i} ---\n{final_result}\n")
    print()

    reference_urls(tools_used)

    resolved_urls = []
    sorted_results = []
    if tools_used and tools_used.results:
        sorted_results = sorted(tools_used.results, key=lambda r: r.score, reverse=True)
        resolved_urls = [
            item.url for item in sorted_results if getattr(item, "url", None)
        ]
        resolved_urls = list(dict.fromkeys(resolved_urls))

    json_payload, stripped_markdown = extract_json_block(final_result)
    if json_payload:
        try:
            parsed = json.loads(json_payload)
            if isinstance(parsed, dict):
                parsed["reference_urls"] = resolved_urls
                json_payload = json.dumps(parsed, indent=2, ensure_ascii=False)
        except (json.JSONDecodeError, ValueError):
            pass
        json_filename = OUTPUT_DIR / f"asset_{i}.json"
        with json_filename.open("w", encoding="utf-8") as json_file:
            json_file.write(json_payload)
        print(f"Saved JSON payload to {json_filename}")
    else:
        stripped_markdown = final_result

    output_folder = "groq_output"
    os.makedirs(output_folder, exist_ok=True)

    md_filename = os.path.join(output_folder, f"asset_{i}.md")

    md_content = "# Asset Resolution Output\n\n"
    md_content += "## Final Result\n\n"
    md_content += f"{stripped_markdown}\n\n"

    md_content += "## Reference URLs\n\n"

    if sorted_results:
        for item in sorted_results:
            md_content += f"- **{item.title}**\n"
            md_content += f"  - URL: {item.url}\n"
            md_content += f"  - Score: {item.score}\n\n"
    else:
        md_content += "_No reference URLs found._\n"

    with open(md_filename, "w", encoding="utf-8") as md_file:
        md_file.write(md_content)

    print(f"Markdown file saved at: {md_filename}")