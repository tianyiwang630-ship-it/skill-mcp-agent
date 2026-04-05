from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LLM_PROFILES_PATH = PROJECT_ROOT / "config" / "llm_profiles.json"


@dataclass(frozen=True)
class LLMProfile:
    name: str
    provider: str
    base_url: str
    api_key: str
    model: str


def load_llm_profile(profile_name: str | None = None) -> LLMProfile:
    config = _load_profiles_config()
    selected_name = profile_name or config["default"]

    profiles = config.get("profiles", {})
    if selected_name not in profiles:
        raise ValueError(f"Unknown LLM profile: {selected_name}")

    raw_profile = profiles[selected_name]
    api_key_env = raw_profile["api_key_env"]
    api_key = os.getenv(api_key_env)
    if not api_key:
        raise ValueError(f"Environment variable not set for LLM profile: {api_key_env}")

    return LLMProfile(
        name=selected_name,
        provider=raw_profile["provider"],
        base_url=raw_profile["base_url"],
        api_key=api_key,
        model=raw_profile["model"],
    )


def _load_profiles_config() -> dict[str, Any]:
    if not LLM_PROFILES_PATH.exists():
        raise FileNotFoundError(f"LLM profile config not found: {LLM_PROFILES_PATH}")

    data = json.loads(LLM_PROFILES_PATH.read_text(encoding="utf-8"))
    if "default" not in data:
        raise ValueError("llm_profiles.json must define a default profile")
    if "profiles" not in data or not isinstance(data["profiles"], dict) or not data["profiles"]:
        raise ValueError("llm_profiles.json must define at least one profile")
    return data
