import os
from google import genai
import re
import time
import argparse
from typing import List, Optional
from dotenv import load_dotenv 

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    raise SystemExit("GOOGLE_API_KEY is not set in the environment. Please set it in your .env file.")

client = genai.Client()

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_QUERIES_FILE = os.path.join(ROOT_DIR, "queries.txt")
DEFAULT_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "gemini_results")
os.makedirs(DEFAULT_OUTPUT_DIR, exist_ok=True)

# Function to make a safe filename from query
def safe_filename(name, out_dir: str):
    # Remove or replace characters not allowed in filenames
    filename = re.sub(r'[\\/:"*?<>|]+', "_", name) + ".md"
    
    # Return full path in the gemini results folder
    return os.path.join(out_dir, filename)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gemini search runner")
    parser.add_argument("input", nargs="?", help="Direct query or @path/to/queries.txt. If omitted, defaults to queries.txt at repo root.")
    parser.add_argument("--query", dest="query", help="Explicit query string (overrides positional input)")
    parser.add_argument("--output-dir", dest="out_dir", default=DEFAULT_OUTPUT_DIR, help="Directory to store results (default: gemini_results)")
    parser.add_argument("--out-file", dest="out_file", help="If set for single query, write result to this file. Example: @llm_response.md or /abs/path.md")
    parser.add_argument("--stdout", dest="to_stdout", action="store_true", help="Also print response content to stdout for single query")
    parser.add_argument("--model", dest="model", default="gemini-2.5-flash", help="Gemini model to use (e.g., gemini-2.5-flash, gemini-2.5-pro, gemini-2.5-flash-lite)")
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
    if not os.path.exists(DEFAULT_QUERIES_FILE):
        raise SystemExit(f"Default queries file not found: {DEFAULT_QUERIES_FILE}")
    with open(DEFAULT_QUERIES_FILE, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def run_query(query: str, model: str, out_dir: str, out_file: Optional[str], to_stdout: bool) -> None:
    print(f"Processing query: {query}")
    prompt = f"""Search for {query}
    Retrieve the most relevant and up-to-date information
    Summarize key specifications
    Include valid, working reference URLs for all sources used
    Give the response in structured format"""
    start_time = time.time()
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config={"tools": [{"google_search": {}}]},
    )
    response_time = time.time() - start_time
    # Determine output file path
    target_path: Optional[str] = None
    if out_file:
        # Support @filename.md shorthand relative to repo root
        target_path = out_file[1:] if out_file.startswith("@") else out_file
        if not os.path.isabs(target_path):
            target_path = os.path.join(ROOT_DIR, target_path)
    else:
        target_path = safe_filename(query, out_dir)

    with open(target_path, "w", encoding="utf-8") as f:
        f.write(f"# Query: {query}\n\n")
        f.write(f"**Response Time:** {response_time:.2f} seconds\n\n")
        f.write(response.text)
    print(f"Saved response to {target_path}")
    if to_stdout:
        print("\n----- Response (stdout) -----\n")
        print(response.text)

if __name__ == "__main__":
    args = parse_args()
    out_dir = args.out_dir if os.path.isabs(args.out_dir) else os.path.join(os.path.dirname(__file__), os.path.basename(args.out_dir))
    os.makedirs(out_dir, exist_ok=True)
    queries = [args.query] if args.query else load_queries_from_arg(args.input)
    for q in queries:
        run_query(q, args.model, out_dir, args.out_file, args.to_stdout)