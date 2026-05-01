"""Cloudnest Pilot entry point.

Usage:
  python run.py --cli     # terminal interface
  python run.py --web     # web interface on http://localhost:8765
  python run.py --demo    # try without API key (canned responses)
  python run.py           # defaults to --web
"""
from __future__ import annotations

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="ocp-agent",
        description="Conversational AI copilot for OpenShift clusters.",
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Run the terminal interface (rich-formatted chat)",
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="Run the web interface (default). Opens http://localhost:8765",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Demo mode — runs with canned responses, no API key needed",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Override WEB_PORT from .env for the web UI",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="ocp-agent 0.1.0",
    )
    args = parser.parse_args()

    # Demo mode bypasses config loading entirely (no API key needed)
    if args.demo:
        return run_demo(args)

    # Real mode — load config (validates API key)
    try:
        from cloudnest_pilot.config import Config
        config = Config.load()
    except SystemExit as e:
        print(f"\n{e}\n")
        print("Tip: try `python run.py --demo` to try without an API key.")
        return 1

    if args.port:
        config.web_port = args.port

    if args.cli:
        from cloudnest_pilot.cli import run_cli
        try:
            run_cli(config)
        except KeyboardInterrupt:
            print("\nGoodbye.")
        return 0

    # Default: web UI
    from cloudnest_pilot.web import run_web
    try:
        run_web(config)
    except KeyboardInterrupt:
        print("\nGoodbye.")
    return 0


def run_demo(args: argparse.Namespace) -> int:
    """Demo mode entry point — no API key needed."""
    print("\n  Cloudnest Pilot — DEMO MODE")
    print("  " + "─" * 40)
    print("  Running with canned responses. No API key required.")
    print("  Try prompts like:")
    print("    'help me deploy a cluster'")
    print("    'show me an IAM policy'")
    print("    'show me an install-config.yaml'")
    print()

    port = args.port or 8765
    
    # Import here to avoid loading config at module level
    from cloudnest_pilot.web import run_web_demo
    
    try:
        run_web_demo(port=port)
    except KeyboardInterrupt:
        print("\nGoodbye.")
    return 0


if __name__ == "__main__":
    sys.exit(main())