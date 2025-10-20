import os
import time
import json
import re
from datetime import datetime, timezone
from groq import Groq
from dotenv import load_dotenv

# -------------------------------
# Setup
# -------------------------------
load_dotenv()

client = Groq(
    api_key=os.getenv("GROQ_API_KEY"),
    default_headers={"Groq-Model-Version": "latest"}
)

USAGE_LOG_PATH = "usage_log.json"
DAILY_LIMIT = 250


# -------------------------------
# Usage Tracking
# -------------------------------
def load_usage():
    """Load API usage tracking file."""
    if os.path.exists(USAGE_LOG_PATH):
        with open(USAGE_LOG_PATH, "r") as f:
            return json.load(f)
    return {}


def save_usage(usage_data):
    """Save usage count per day."""
    with open(USAGE_LOG_PATH, "w") as f:
        json.dump(usage_data, f)


def check_and_update_usage():
    """Increment usage counter, prevent exceeding daily limit."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    usage = load_usage()

    count = usage.get(today, 0)
    if count >= DAILY_LIMIT:
        print(f"⚠️ Daily limit of {DAILY_LIMIT} reached for {today}. No more requests allowed.")
        return False

    usage[today] = count + 1
    save_usage(usage)
    print(f"ℹ️ API calls today: {usage[today]} / {DAILY_LIMIT}")
    return True


# -------------------------------
# Helpers
# -------------------------------
def sanitize_filename(name: str) -> str:
    """Make a safe filename by replacing spaces and removing invalid characters."""
    safe_name = re.sub(r"[^\w\-]+", "_", name.strip())
    return safe_name[:100]


def log_performance(query, output_path, duration, model):
    """Append performance details to performance.txt, skip if already logged."""
    perf_path = "performance.txt"
    safe_name = os.path.basename(output_path)
    entry_header = f"[{safe_name}]"

    # Avoid duplicate entries
    if os.path.exists(perf_path):
        with open(perf_path, "r", encoding="utf-8") as f:
            if entry_header in f.read():
                print(f"📄 Performance already logged for: {safe_name}")
                return

    with open(perf_path, "a", encoding="utf-8") as f:
        f.write(
            f"{entry_header}\n"
            f"Query: {query}\n"
            f"Model: {model}\n"
            f"Time: {datetime.now(timezone.utc).isoformat()}\n"
            f"Duration: {duration:.2f} sec\n"
            f"Output: {output_path}\n"
            f"{'-'*40}\n"
        )
    print(f"📊 Logged performance for: {safe_name}")


# -------------------------------
# Core Query Function
# -------------------------------
def query_with_compound(query: str, model: str, instructions: str, output_path: str) -> str:
    """
    Runs one LLM query, extracts JSON (even if multiple exist), 
    and saves the final structured JSON to a .json file.
    """
    if not check_and_update_usage():
        print("Aborting query due to daily limit reached.")
        return ""

    messages = [
        {"role": "system", "content": instructions},
        {"role": "user", "content": query}
    ]

    print(f"\n🔍 Processing Query: {query}\n")
    start_time = time.time()

    # Stream LLM response
    stream = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.7,
        max_completion_tokens=2048,
        top_p=1,
        stream=True,
    )

    content = ""
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            print(delta, end="", flush=True)
            content += delta

    duration = time.time() - start_time
    print(f"\n⏱️ Took {duration:.2f} seconds")

    # -------------------------------
    # 🔍 Extract all JSON blocks
    # -------------------------------
    json_blocks = re.findall(r"```json\s*(\{.*?\})\s*```", content, re.DOTALL)

    if not json_blocks:
        # fallback: try to catch any JSON-like structure even without ```json
        json_blocks = re.findall(r"(\{[\s\S]*?\})", content)

    if not json_blocks:
        print("⚠️ No JSON found in response. Saving full response instead.")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content.strip() + "\n")
        return content.strip()

    # Pick the last JSON block (most complete one)
    json_str = json_blocks[-1].strip()

    # -------------------------------
    # ✅ Validate and save JSON
    # -------------------------------
    try:
        parsed_json = json.loads(json_str)
        is_valid_json = True
    except json.JSONDecodeError:
        print("⚠️ JSON parsing failed — saving raw JSON text instead.")
        parsed_json = None
        is_valid_json = False

    json_output_path = os.path.splitext(output_path)[0] + ".json"

    with open(json_output_path, "w", encoding="utf-8") as f:
        if is_valid_json:
            json.dump(parsed_json, f, indent=4, ensure_ascii=False)
        else:
            f.write(json_str)

    # -------------------------------
    # 🧾 Optional: save intermediate JSONs for debugging
    # -------------------------------
    if len(json_blocks) > 1:
        debug_dir = os.path.splitext(output_path)[0] + "_partials"
        os.makedirs(debug_dir, exist_ok=True)
        for idx, block in enumerate(json_blocks, 1):
            block_path = os.path.join(debug_dir, f"partial_{idx}.json")
            with open(block_path, "w", encoding="utf-8") as f:
                try:
                    f.write(json.dumps(json.loads(block), indent=4, ensure_ascii=False))
                except json.JSONDecodeError:
                    f.write(block)
        print(f"💾 Saved {len(json_blocks)} JSON blocks in {debug_dir}")

    # -------------------------------
    # 🕒 Log performance
    # -------------------------------
    log_performance(query, json_output_path, duration, model)

    print(f"✅ Final JSON saved to: {json_output_path}\n")
    return json_str



# -------------------------------
# Query Processing Loop
# -------------------------------
def process_queries_file(filename="queries.txt", output_dir="results", skip_existing=True):
    """Reads queries from a file and saves JSON results."""
    if not os.path.exists(filename):
        print(f"❌ File '{filename}' not found.")
        return

    os.makedirs(output_dir, exist_ok=True)

    with open(filename, "r", encoding="utf-8") as f:
        queries = [line.strip() for line in f if line.strip()]

    total = len(queries)
    for i, raw_query in enumerate(queries, start=1):
        query = f"{raw_query}"

        instructions = (
            f"Search for {raw_query}\n"
            "Provide the Product ID\n"
            "Provide the Brand Product which is description\n"
            "Provide the Product SKU\n"
            "Provide the Brand Name\n"
            "Provide the Specifications\n"
            "Provide the References (URLs) used for search\n"
            "Give the response in structured JSON format\n"
            "Make the Specifications in a nested format\n"
        )

        safe_name = sanitize_filename(raw_query)
        output_path = os.path.join(output_dir, f"{safe_name}.md")

        # Skip existing JSON files
        json_output_path = os.path.splitext(output_path)[0] + ".json"
        if skip_existing and os.path.exists(json_output_path) and os.path.getsize(json_output_path) > 0:
            print(f"⏩ Skipping existing JSON: {json_output_path}")
            continue

        print(f"\n({i}/{total}) Running query: {raw_query}")
        query_with_compound(query, "groq/compound", instructions, output_path)

        # Prevent API rate issues
        time.sleep(10)


# -------------------------------
# Run
# -------------------------------
if __name__ == "__main__":
    process_queries_file("queries.txt", output_dir="groq_results", skip_existing=True)
