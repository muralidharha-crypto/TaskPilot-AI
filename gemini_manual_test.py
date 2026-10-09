import os
import sys

from dotenv import load_dotenv
from google import genai

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("❌ GEMINI_API_KEY was not found.")
    sys.exit()

print("✅ GEMINI_API_KEY loaded successfully.")
print("Key length:", len(api_key))

client = genai.Client(api_key=api_key)

response = client.models.generate_content(
    model="gemini-3.8-flash",
    contents="Say exactly: TaskPilot Gemini connection successful."
)

print("Gemini response:")
print(response.text)