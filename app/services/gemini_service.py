import os
from dotenv import load_dotenv
from google import genai

load_dotenv()


class GeminiService:
    """Service for communicating with Google's Gemini API."""

    _client = None

    @classmethod
    def get_client(cls):
        if cls._client is None:
            api_key = os.getenv("GEMINI_API_KEY")

            if not api_key:
                raise RuntimeError(
                    "GEMINI_API_KEY is not configured. "
                    "Add it to the project's .env file."
                )

            cls._client = genai.Client(api_key=api_key)

        return cls._client

    @classmethod
    def research(cls, topic):
        """
        Research a topic using Gemini with Google Search grounding.
        """

        client = cls.get_client()

        prompt = f"""
You are the Research Agent inside TaskPilot AI.

Research the following topic:

{topic}

Your job is to provide an accurate, useful academic-quality answer.

Requirements:
1. Explain the topic clearly.
2. Identify the key concepts.
3. Give important findings.
4. Explain benefits and advantages.
5. Explain risks, limitations and disadvantages.
6. Give real-world examples.
7. Give practical next steps for the user.
8. Use reliable and verifiable information.
9. Do NOT invent papers, authors, statistics, URLs or citations.
10. If information cannot be verified, explicitly say so.

Return the answer as structured information that TaskPilot can display.
"""

        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt,
            config={
                "tools": [
                    {"google_search": {}}
                ]
            }
        )

        return response