"""Local runtime environment profile for agent-alpha subprocesses."""

from __future__ import annotations

import json
import os
from pathlib import Path


PROFILE_RELATIVE_PATH = Path("config") / "runtime_env.local.json"
REDACTION = "[REDACTED]"


def profile_path(project_root: Path) -> Path:
    return Path(project_root).resolve() / PROFILE_RELATIVE_PATH


def load_runtime_env(project_root: Path) -> dict[str, str]:
    path = profile_path(project_root)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    env = data.get("env", data)
    if not isinstance(env, dict):
        return {}
    return {str(key): str(value) for key, value in env.items() if _valid_env_name(str(key))}


def subprocess_env(project_root: Path, base_env: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(base_env or os.environ)
    env.update(load_runtime_env(project_root))
    return env


def redact_secrets(text: str | None, project_root: Path) -> str | None:
    if text is None:
        return None
    redacted = text
    for value in load_runtime_env(project_root).values():
        if len(value) >= 4:
            redacted = redacted.replace(value, REDACTION)
    return redacted


def _valid_env_name(name: str) -> bool:
    if not name:
        return False
    first = name[0]
    if not (first.isalpha() or first == "_"):
        return False
    return all(char.isalnum() or char == "_" for char in name)
