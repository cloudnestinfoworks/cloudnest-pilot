"""Verify Claude API connectivity.

Run this FIRST, before trying to start the web/CLI interface.
It does exactly one thing: send a "hello" to Claude and print the response.

If this works, the main tool will work too.
If this fails, fix the issue before running run.py.

Usage:
    python verify_api.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def main() -> int:
    # Load .env from the script's directory
    script_dir = Path(__file__).resolve().parent
    env_path = script_dir / ".env"
    load_dotenv(env_path)

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

    print("\n  OCP Agent — API connectivity check")
    print("  " + "─" * 40)

    if not api_key:
        print("  ✗ ANTHROPIC_API_KEY is not set.")
        print(f"     Edit {env_path} and add your key.")
        return 1

    if api_key.startswith("sk-ant-api03-...") or len(api_key) < 40:
        print("  ✗ ANTHROPIC_API_KEY looks like the placeholder value.")
        print(f"     Edit {env_path} and paste your real key.")
        print("     Get one from https://console.anthropic.com/settings/keys")
        return 1

    print(f"  ✓ API key found ({api_key[:15]}...)")
    print(f"  ✓ Using model: {model}")
    print("  → Calling Claude API...")

    try:
        from anthropic import Anthropic
    except ImportError:
        print("  ✗ 'anthropic' package not installed.")
        print("     Run: pip install -r requirements.txt")
        return 1

    try:
        client = Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=100,
            messages=[
                {
                    "role": "user",
                    "content": "Reply with exactly: 'OCP Agent API test OK'"
                }
            ],
        )
        text = ""
        for block in response.content:
            if getattr(block, "type", None) == "text":
                text += block.text

        print(f"  ← Claude responded: {text.strip()}")
        print()
        print("  ✓ All good! You can now run:")
        print("     python run.py --web   (for web UI)")
        print("     python run.py --cli   (for terminal UI)")
        print()
        return 0

    except Exception as e:  # noqa: BLE001 — catch-all for test script
        print(f"  ✗ API call failed: {type(e).__name__}: {e}")
        print()
        print("  Common causes:")
        print("   • Invalid API key — check https://console.anthropic.com/settings/keys")
        print("   • No billing set up — add payment at https://console.anthropic.com/settings/billing")
        print("   • Network issue — check your internet connection")
        print("   • Firewall blocking api.anthropic.com")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())
