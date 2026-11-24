"""One Sarvam chat completion call: proves the API key and SDK work."""

import os

from dotenv import load_dotenv
from sarvamai import SarvamAI

load_dotenv()  # reads SARVAM_API_KEY from the .env file in this folder

api_key = os.environ.get("SARVAM_API_KEY", "").strip()
if not api_key:
    raise SystemExit("SARVAM_API_KEY is not set. Paste your key into the .env file, then run this again.")

client = SarvamAI(api_subscription_key=api_key)

response = client.chat.completions(
    model="sarvam-105b-conversations",
    messages=[{"role": "user", "content": "Namaste! Ek line mein batao, tum kaun ho?"}],
)

print(response.choices[0].message.content)
