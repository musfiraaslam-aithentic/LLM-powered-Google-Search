import json
import os
from dotenv import load_dotenv
from groq import Groq

def main():
    load_dotenv()
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("GROQ_API_KEY missing")
        return 1

    client = Groq(api_key=api_key)

    try:
        response = client.chat.completions.create(
            model="groq/compound",
            messages=[
                {"role": "system", "content": "Return only raw JSON."},
                {"role": "user", "content": "Give UTC time and a fun fact in JSON."},
            ],
            max_completion_tokens=256
        )
    except Exception as exc:
        print("Groq health check failed:\n", exc)
        return 2

    content = response.choices[0].message.content.strip()

    try:
        print(json.dumps(json.loads(content), indent=2))
    except:
        print("Invalid JSON received:\n", content)

if __name__ == "__main__":
    main()
