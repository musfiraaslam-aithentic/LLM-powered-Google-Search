# Asset Data Enrichment Service

A microservice that enriches product's data using Gemini and Groq with web search. It takes product's 

* Metadata 
* Tech Groups (Optional)
* Tech Types (Optional)

as input and returns structured data (brand info, matched tech type/group, product description, product's features, reference URLs) in the form of json. 


## Requirements
- Python 3.9+ (tested on 3.12)
- `GOOGLE_API_KEY` https://aistudio.google.com/app/api-keys
- `GROQ_API_KEY` https://console.groq.com/keys

## Setup
- Create and activate a virtual environment:
  ```bash
  python -m venv venv
  source venv/bin/activate
  ```
- Install dependencies:
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
uvicorn main:app --reload 
```

## Quick Test
```bash
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{
  "metadata": {
    "hardware_data": {
      "type": "docking station",
      "model": "Inspiron 7472",
      "specs": {
        "cpus": null,
        "uuid": "4C4C4544-0043-5910-8044-B3C04F435132",
        "sounds": [
          {
            "name": "Intel(R) Display Audio",
            "description": "Intel(R) Display Audio",
            "manufacturer": "Intel(R) Corporation"
          },
          {
            "name": "Realtek Audio",
            "description": "Realtek Audio",
            "manufacturer": "Realtek"
          }
        ]
      },
      "manufacturer": "Dell",
      "serial_number": "3CYDCQ2"
    }
  },
  "tech_groups": [
    "Desktops", "Laptops", "Tablets"
  ],
  "tech_types": [
    "Hardware" , "Software"
  ]
}
'
```
- metadata → must be a single object (dict)
- tech_groups → optional list of strings
- tech_types → optional list of strings


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
- This microservice handles exactly one asset at a time, not a batch!
- We have added .env file in repository just for testing, you can update it later.
- Tech groups and techtypes in data folder `data/tech_groups.json` and '`data/tech_types.json` (last fetched: Nov 2025), could also be used in microservice as default Tech groups and type, we have commented that part, you could utilize that as well.
