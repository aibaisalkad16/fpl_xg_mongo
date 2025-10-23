import os
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

try:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"user", "content": "Hello, are you working?"}]
    )
    print("✅ OpenAI connection successful!")
    print("Assistant replied:", response.choices[0].message.content)
except Exception as e:
    print("❌ OpenAI connection failed:")
    print(e)
