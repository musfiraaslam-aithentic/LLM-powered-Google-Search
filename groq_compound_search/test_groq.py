import os
import time
import json
import re
import argparse
from typing import List, Optional
from datetime import datetime, timezone
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise SystemExit("GROQ_API_KEY is not set in the environment. Please set it in your .env file.")

client = Groq(
    api_key=GROQ_API_KEY,
    default_headers={"Groq-Model-Version": "latest"}
)

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
USAGE_LOG_PATH = os.path.join(os.path.dirname(__file__), "usage_log.json")
DAILY_LIMIT = 250

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
        print(f"Daily limit of {DAILY_LIMIT} reached for {today}. No more requests allowed.")
        return False

    usage[today] = count + 1
    save_usage(usage)
    print(f"API calls today: {usage[today]} / {DAILY_LIMIT}")
    return True

def sanitize_filename(name: str) -> str:
    """Make a safe filename by replacing spaces and removing invalid characters."""
    safe_name = re.sub(r"[^\w\-]+", "_", name.strip())
    return safe_name[:100] 

def query_with_compound(query: str, model: str, instructions: str, output_path: str) -> str:
    """Runs one LLM query and writes the result to output_path."""
    if not check_and_update_usage():
        print("Aborting query due to daily limit reached.")
        return ""

    messages = [
        {"role": "system", "content": instructions},
        {"role": "user", "content": query}
    ]

    print(f"\nProcessing Query: {query}\n")
    start_time = time.time()

    stream = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.7,
        max_completion_tokens=1024,
        top_p=1,
        stream=True,
    )

    content = ""
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            print(delta, end="", flush=True)
            content += delta

    print(f"\nTook {time.time() - start_time:.2f} seconds")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content.strip() + "\n")

    print(f"Saved to: {output_path}\n")
    return content.strip()

def process_queries_file(filename="queries.txt", output_dir="results", skip_existing=True):
    """
    Reads each query from queries.txt, builds search string,
    sends to LLM, and saves each result as a Markdown file.
    """
    # Ensure filename is resolved to project root
    filename = filename if os.path.isabs(filename) else os.path.join(ROOT_DIR, filename)

    if not os.path.exists(filename):
        print(f"File '{filename}' not found.")
        return

    # Ensure output directory is within this module's results folder when relative
    if not os.path.isabs(output_dir):
        output_dir = os.path.join(os.path.dirname(__file__), output_dir)
    os.makedirs(output_dir, exist_ok=True)

    with open(filename, "r", encoding="utf-8") as f:
        queries = [line.strip() for line in f if line.strip()]

    total = len(queries)
    for i, raw_query in enumerate(queries, start=1):
        query = f"{raw_query}"

        instructions = (
            f"Search for {raw_query}\n"
            "Provide the specifications\n"
            "Provide the References (URLs) used for search\n"
            "Give the response in structured format\n"
        )

        safe_name = sanitize_filename(raw_query)
        output_path = os.path.join(output_dir, f"{safe_name}.md")

        if skip_existing and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            print(f"Skipping existing file: {output_path}")
            continue

        print(f"\n({i}/{total}) Running query: {raw_query}")
        query_with_compound(query, "groq/compound", instructions, output_path)

        time.sleep(10)

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Groq compound search runner")
    parser.add_argument("input", nargs="?", help="Direct query or @path/to/queries.txt. If omitted, defaults to queries.txt at repo root.")
    parser.add_argument("--query", dest="query", help="Explicit query string (overrides positional input)")
    parser.add_argument("--output-dir", dest="out_dir", default="groq_results", help="Directory to store results (default: groq_results)")
    parser.add_argument("--skip-existing", dest="skip_existing", action="store_true", help="Skip writing if output file already exists and is non-empty")
    parser.add_argument("--out-file", dest="out_file", help="If set for single query, write result to this file. Example: @llm_response.md or /abs/path.md")
    parser.add_argument("--stdout", dest="to_stdout", action="store_true", help="Also print response content to stdout for single query")
    return parser.parse_args()


def load_queries_from_arg(arg_value: str) -> List[str]:
    if arg_value and arg_value.startswith("@"):
        file_path = arg_value[1:]
        if not os.path.isabs(file_path):
            file_path = os.path.join(ROOT_DIR, file_path)
        if not os.path.exists(file_path):
            raise SystemExit(f"File not found: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    if arg_value:
        return [arg_value]
    default_file = os.path.join(ROOT_DIR, "queries.txt")
    if not os.path.exists(default_file):
        raise SystemExit(f"Default queries file not found: {default_file}")
    with open(default_file, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


# ---------- Run ----------
if __name__ == "__main__":
    args = parse_args()
    out_dir = args.out_dir if os.path.isabs(args.out_dir) else os.path.join(os.path.dirname(__file__), args.out_dir)
    os.makedirs(out_dir, exist_ok=True)
    queries = [args.query] if args.query else load_queries_from_arg(args.input)
    for q in queries:
        # Determine output path
        if args.out_file and len(queries) == 1:
            target_path: Optional[str] = args.out_file[1:] if args.out_file.startswith("@") else args.out_file
            if not os.path.isabs(target_path):
                target_path = os.path.join(ROOT_DIR, target_path)
        else:
            safe_name = sanitize_filename(q)
            target_path = os.path.join(out_dir, f"{safe_name}.md")

        if args.skip_existing and os.path.exists(target_path) and os.path.getsize(target_path) > 0:
            print(f"Skipping existing file: {target_path}")
            continue

        instructions = (
            f"Search for {q}\n"
            "Provide the specifications\n"
            "Provide the References (URLs) used for search\n"
            "Give the response in structured format\n"
        )
        content = query_with_compound(q, "groq/compound", instructions, target_path)
        if args.to_stdout and content:
            print("\n----- Response (stdout) -----\n")
            print(content)
        time.sleep(10)