## LLM-powered Google Search 

This project uses language models from Groq and Google Gemini to search the web and extract relevant product information with reference URLs. Results are stored in Markdown format for each query.

### Requirements
- Dependencies are listed in `requirements.txt`.
- Set API keys for [Google Gemini API keys](https://aistudio.google.com/api-keys) and [Groq API keys](https://console.groq.com/keys). Add them to your shell environment or the `.env` file.

### Setup
1. Create a virtual environment and install dependencies:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. Create a `.env` file in the project root with your API keys:
```bash
GOOGLE_API_KEY=your_google_api_key
GROQ_API_KEY=your_groq_api_key
```

3. Keep your queries in `queries.txt` (one per line).

### Running
- Run the Gemini search script (default reads `queries.txt` at repo root):
```bash
python gemini_search/test_gemini.py
```
  - Output: `gemini_search/gemini_results/*.md`

- Run the Groq compound search script (default reads `queries.txt` at repo root):
```bash
python groq_compound_search/test_groq.py
```
  - Output: `groq_compound_search/groq_results/*.md`


### Gemini model options
The Gemini script currently uses `gemini-2.5-flash`. You can also try:
- `gemini-2.5-pro`
- `gemini-2.5-flash-lite`

Where to change it: in `gemini_search/test_gemini.py`, update the `model` parameter passed to `client.models.generate_content`.

### CLI usage
Both scripts accept either a direct query or a file of queries with the `@` prefix. Examples (run from project root):

- Single query (Gemini):
```bash
python gemini_search/test_gemini.py --query "Philips 196V4"
```

- Queries from file (Gemini):
```bash
python gemini_search/test_gemini.py @queries.txt
```

- Specify output directory (Gemini) and model:
```bash
python gemini_search/test_gemini.py @queries.txt --output-dir gemini_search/gemini_results --model gemini-2.5-pro
```

- Single query (Groq):
```bash
python groq_compound_search/test_groq.py --query "Philips 196V4"
```

- Queries from file (Groq):
```bash
python groq_compound_search/test_groq.py @queries.txt
```

- Specify output directory and skip existing (Groq):
```bash
python groq_compound_search/test_groq.py @queries.txt --output-dir groq_compound_search/groq_results 
```



