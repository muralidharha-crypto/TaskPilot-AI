import os
import sys

from dotenv import load_dotenv
from google import genai

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("❌ GEMINI_API_KEY not found")
    sys.exit()

client = genai.Client(api_key=api_key)

response = client.models.generate_content(
    model="gemini-3.8-flash",
    contents="What is the difference between cloud computing and edge computing?",
    config={
        "tools": [
            {"google_search": {}}
        ]
    }
)

print("✅ Gemini + Google Search successful!")
print()
print(response.text)