# Note: This is a legacy approach for Gemini 1.5 models.
# The 'google_search' tool is recommended for all new development.
import os
from google import genai
from google.genai import types
import dotenv
dotenv.load_dotenv()
GOOGLE_API_KEY_1 = os.getenv("GOOGLE_API_KEY_1")
if not GOOGLE_API_KEY_1:
    raise SystemExit("GOOGLE_API_KEY_1 not set in environment!")

client = genai.Client(api_key=GOOGLE_API_KEY_1)

grounding_tool = types.Tool(
    google_search=types.GoogleSearch()
)

config = types.GenerateContentConfig(
    tools=[grounding_tool]
)

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="what is date today",
    config=config,
)

print(response.text)

# i prefer flash 2 001