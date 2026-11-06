"""
Saves your Anthropic API key into the private .env file. Run once:

    python save_api_key.py

Paste the key when asked. Nothing shows on screen while you paste: that is on purpose.
"""

from getpass import getpass

from src.load import PROJECT_ROOT

key = getpass("Paste your Anthropic API key, then press Enter: ").strip()
if not key.startswith("sk-"):
    raise SystemExit("That doesn't look like an Anthropic key (it should start with sk-). Nothing saved.")
(PROJECT_ROOT / ".env").write_text(f"ANTHROPIC_API_KEY={key}\n", encoding="utf-8")
print("Saved to .env. You can close the key page now. Next: python check_setup.py")
