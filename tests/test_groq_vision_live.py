"""
Live diagnostic test: calls Ollama qwen2.5vl:3b exactly the same way llm_scorer.py does.
Run: .\venv\Scripts\python tests\test_groq_vision_live.py
"""
import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from openai import OpenAI

THUMB_DIR = Path("./storage/thumbnails")
MODEL = "qwen2.5vl:3b"
BASE_URL = "http://localhost:11434/v1"

client = OpenAI(api_key="ollama", base_url=BASE_URL)

# Grab a real thumbnail from storage
thumb_files = sorted(THUMB_DIR.rglob("*_thumb_01.jpg"))[:1]
base64_imgs = []
if thumb_files:
    with open(thumb_files[0], "rb") as f:
        base64_imgs.append(base64.b64encode(f.read()).decode("utf-8"))
    print(f"[TEST] Using thumbnail: {thumb_files[0]}")
else:
    print("[TEST] No thumbnails found — running text-only mode")

system_prompt = (
    "You are a professional video editor assistant.\n"
    "Analyze the provided clip metadata and/or visual keyframes. "
    "You MUST respond with a single valid JSON object containing exactly the keys 'tags' and 'summary' (no other keys).\n"
    "  \"tags\": array of 3-8 lowercase single-word or short-phrase descriptors.\n"
    "  \"summary\": one sentence describing the video.\n"
    "Do not include any introductory conversational text, markdown formatting (like ```json), or backticks. "
    "Your response must start with '{' and end with '}'."
)

user_content = [
    {
        "type": "text",
        "text": (
            "You are analyzing a sequence of keyframes extracted from a single video clip.\n"
            "Review these keyframe images visually to understand the core subject, action, setting, "
            "and context of the video. Then combine your visual analysis with the metadata below:\n\n"
            "Filename: test_exterior.mp4\n"
            "Duration: 15.0s\n"
            "Resolution: 1920x1080 @ 30.0fps\n"
            "Blur score: 7.2\n"
            "Stability score: 6.8\n"
            "Exposure score: 7.1\n"
        ),
    }
]

for img in base64_imgs:
    user_content.append({
        "type": "image_url",
        "image_url": {"url": f"data:image/jpeg;base64,{img}"}
    })

print(f"[TEST] Sending {'multimodal' if base64_imgs else 'text-only'} request to {MODEL}...")

try:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=0.3,
        max_tokens=2048,
        # NOTE: no response_format here — qwen2.5vl doesn't support it with images
    )
    raw = response.choices[0].message.content or "{}"
    print(f"\n[TEST] RAW RESPONSE ({len(raw)} chars):")
    print(repr(raw))
    print()

    # Strip markdown if present
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    data = json.loads(cleaned)
    print("[TEST] ✅ JSON parsed successfully!")
    print(f"  tags:    {data.get('tags')}")
    print(f"  summary: {data.get('summary')}")

except json.JSONDecodeError as e:
    print(f"[TEST] ❌ JSON parse failed: {e}")
    print(f"  Cleaned raw: {repr(cleaned[:500])}")
    sys.exit(1)
except Exception as e:
    print(f"[TEST] ❌ API call failed: {type(e).__name__}: {e}")
    sys.exit(1)
