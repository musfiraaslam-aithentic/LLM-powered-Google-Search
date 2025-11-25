# Asset Data Enrichment Service

FastAPI microservice that enriches asset metadata using Gemini and Groq with web search. It takes asset's metadata and Techgroups list as input and returns structured data (brand, tech type/group, product info, reference URLs). 

Default tech groups are loaded from `data/tech_groups.json` (last fetched: Nov 2025).

## Requirements
- Python 3.9+ (tested on 3.12)
- Google API key (`GOOGLE_API_KEY`)
- Groq API key (`GROQ_API_KEY`)

## Setup
```bash
pip install -r requirements.txt
```
Create `.env` in the project root:
```
GOOGLE_API_KEY=your_google_api_key
GROQ_API_KEY=your_groq_api_key
```
Request counters are written to `logs/requests.json`.

## Run
```bash
uvicorn main:app --reload --port 8000
```

## Quick Test
```bash
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{
        "metadata": {
          "os": "Windows 11 Home",
          "cpu": "Intel(R) Core(TM) i5-1035G4 CPU @ 1.10GHz",
          "ram": 7778
        },
        "tech_groups": ["Notebooks", "Servers", "Monitors", "Desktops"]
      }'
```

Expected response shape:
```json
{
  "status": "success",
  "message": "Asset successfully enriched.",
  "result": {
    "brand": "...",
    "brand_country": "...",
    "brand_domain": "...",
    "tech_group": "...",
    "tech_type": "...",
    "product_id": "...",
    "product_desc": "...",
    "product_features": {},
    "reference_urls": []
  }
}
```

## Notes
- If `tech_groups` is omitted, the service defaults to the full list in `data/tech_groups.json`.
- We have added .env file in repository just for testing, you can update it later.
- Request counts per model are tracked in `logs/requests.json`.
