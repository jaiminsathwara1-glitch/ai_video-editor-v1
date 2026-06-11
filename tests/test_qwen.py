from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)

try:
    model = os.getenv("OPENAI_MODEL")
    print(f"Testing local Qwen model: {model}")
    print(f"Base URL: {os.getenv('OPENAI_BASE_URL')}")
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": "Analyze this metadata: clip name is IMG_1029.mp4. What kind of room is this likely to be if it has a sofa?"}
        ]
    )
    print("Success!")
    print(response.choices[0].message.content)
except Exception as e:
    print(f"Error: {e}")
