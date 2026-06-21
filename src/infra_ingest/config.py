"""Configuration helpers for infra-ingest."""

import os
from pathlib import Path

from dotenv import load_dotenv


def resolve_env_path(env_path, base_dir):
    """Resolve an env file path relative to the project directory."""
    path = Path(env_path).expanduser()
    if not path.is_absolute():
        path = Path(base_dir) / path
    return path


def load_environment(env_path):
    """Load environment variables from a .env file with python-dotenv."""
    path = Path(env_path)
    if not path.exists():
        return False
    return load_dotenv(path, override=True)


def find_vault_root(start_path):
    """Walk upward until an Obsidian vault root is found."""
    current = Path(start_path).expanduser().resolve()
    if current.is_file():
        current = current.parent

    while True:
        if (current / ".obsidian").is_dir():
            return str(current)
        if current.parent == current:
            return None
        current = current.parent


def resolve_vault_path(script_dir):
    """Resolve the Obsidian vault path from env, discovery, or default output."""
    configured = os.getenv("OBSIDIAN_VAULT_PATH")
    if configured:
        vault_path = Path(configured).expanduser()
        vault_path.mkdir(parents=True, exist_ok=True)
        return str(vault_path), "configured"

    discovered = find_vault_root(script_dir)
    if discovered:
        return discovered, "discovered"

    fallback = Path.home() / "Documents" / "Whisper转写笔记"
    return str(fallback), "fallback"
