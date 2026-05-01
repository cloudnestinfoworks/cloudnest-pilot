"""Configuration loader.

Reads settings from environment variables and .env file. Validates critical
settings and creates working directories on first run.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load .env if it exists, in the repo root
_repo_root = Path(__file__).resolve().parent.parent
load_dotenv(_repo_root / ".env", override=False)


@dataclass
class Config:
    """Runtime configuration."""

    anthropic_api_key: str
    anthropic_model: str
    pull_secret_path: Path
    openshift_install_path: str  # "" means use PATH
    clusters_dir: Path
    web_port: int
    terminal_theme: str
    history_log: Path

    @classmethod
    def load(cls) -> "Config":
        """Load from environment, creating dirs as needed."""
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not api_key or api_key.startswith("sk-ant-api03-...") or api_key == "":
            raise SystemExit(
                "ANTHROPIC_API_KEY is not set.\n"
                "Edit .env and set your Claude API key from "
                "https://console.anthropic.com/settings/keys"
            )

        model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

        pull_secret = Path(
            os.environ.get("PULL_SECRET_PATH", "~/.ocp-agent/pull-secret.json")
        ).expanduser()

        openshift_install = os.environ.get("OPENSHIFT_INSTALL_PATH", "").strip()

        clusters_dir = Path(
            os.environ.get("CLUSTERS_DIR", "~/.ocp-agent/clusters")
        ).expanduser()
        clusters_dir.mkdir(parents=True, exist_ok=True)

        history_log = clusters_dir.parent / "history.log"
        history_log.parent.mkdir(parents=True, exist_ok=True)
        history_log.touch(exist_ok=True)

        web_port = int(os.environ.get("WEB_PORT", "8765"))
        theme = os.environ.get("TERMINAL_THEME", "dark")

        return cls(
            anthropic_api_key=api_key,
            anthropic_model=model,
            pull_secret_path=pull_secret,
            openshift_install_path=openshift_install,
            clusters_dir=clusters_dir,
            web_port=web_port,
            terminal_theme=theme,
            history_log=history_log,
        )
