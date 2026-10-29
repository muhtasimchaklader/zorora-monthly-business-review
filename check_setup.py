"""
Session 1 setup check. Run from the project folder:

    python check_setup.py

It confirms the packages load and sends one tiny test message to Claude.
Cost of the test message: well under one cent.
"""

import sys

print("1. Checking packages...")
try:
    import anthropic
    import docx  # python-docx
    import pandas
except ImportError as e:
    sys.exit(f"   Missing package: {e.name}. Rerun the pip install command.")
print(f"   OK  pandas {pandas.__version__}, anthropic {anthropic.__version__}")

print("2. Checking the API key file...")
from src.load import load_settings
from src.apikey import get_api_key

key = get_api_key()
print("   OK  key found (not shown)")

print("3. Sending one test message to Claude...")
model = load_settings()["model"]
client = anthropic.Anthropic(api_key=key)
try:
    reply = client.messages.create(
        model=model,
        max_tokens=20,
        messages=[{"role": "user", "content": "Reply with exactly: setup works"}],
    )
except anthropic.AuthenticationError:
    sys.exit("   FAILED: the key was rejected. Create a new key and paste it into .env again.")
except anthropic.APIStatusError as e:
    sys.exit(f"   FAILED: {e.status_code} {e.message}. Check Billing shows credit.")
except anthropic.APIConnectionError:
    sys.exit("   FAILED: could not reach Anthropic. Check your internet connection.")

print(f"   OK  Claude replied: {reply.content[0].text.strip()}")
print("\nSETUP COMPLETE.")
