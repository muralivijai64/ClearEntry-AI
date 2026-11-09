
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
model_name = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

if not api_key:
    raise RuntimeError("GROQ_API_KEY is missing from backend/.env")

client = OpenAI(
    api_key=api_key,
    base_url="https://api.groq.com/openai/v1",
    timeout=60.0,
    max_retries=2,
)

try:
    print("Checking Groq API...")

    models = client.models.list()
    print("Authentication successful!")

    print("\nTesting model:", model_name)

    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {
                "role": "user",
                "content": "Reply with exactly: ClearEntry AI Groq connection successful."
            }
        ],
    )

    print("\nSUCCESS!")
    print(response.choices[0].message.content)

except Exception as error:
    print("\nGroq API request failed:")
    print(type(error).__name__)
    print(str(error))

finally:
    client.close()
