from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("GEMINI_API_KEY"),
    base_url=os.getenv("GEMINI_BASE_URL"),
)

try:
    model = "models/gemini-3.5-flash"
    print(f"Testing Gemini model: {model}")
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": "Hello"}
        ]
    )
    print("Success!")
    print(response.choices[0].message.content)
except Exception as e:
    print(f"Error: {e}")
