import json
from pathlib import Path

import pytest

from tests.conftest import cleanup_test_dir, make_test_dir
from agent.core.llm_profiles import LLMProfile, load_llm_profile


def test_load_llm_profile_uses_default_profile(monkeypatch):
    tmp_dir = make_test_dir("llm-profiles")
    try:
        config_dir = tmp_dir / "config"
        config_dir.mkdir(parents=True)
        profile_file = config_dir / "llm_profiles.json"
        profile_file.write_text(
            json.dumps(
                {
                    "default": "kimi-fast",
                    "profiles": {
                        "kimi-fast": {
                            "provider": "kimi",
                            "base_url": "https://kimi.example/v1",
                            "api_key_env": "TEST_KIMI_API_KEY",
                            "model": "kimi-k2",
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr("agent.core.llm_profiles.LLM_PROFILES_PATH", profile_file)
        monkeypatch.setenv("TEST_KIMI_API_KEY", "kimi-secret")

        profile = load_llm_profile()

        assert profile == LLMProfile(
            name="kimi-fast",
            provider="kimi",
            base_url="https://kimi.example/v1",
            api_key="kimi-secret",
            model="kimi-k2",
        )
    finally:
        cleanup_test_dir(tmp_dir)


def test_load_llm_profile_by_name(monkeypatch):
    tmp_dir = make_test_dir("llm-profile-select")
    try:
        config_dir = tmp_dir / "config"
        config_dir.mkdir(parents=True)
        profile_file = config_dir / "llm_profiles.json"
        profile_file.write_text(
            json.dumps(
                {
                    "default": "openai-main",
                    "profiles": {
                        "openai-main": {
                            "provider": "openai",
                            "base_url": "https://api.openai.com/v1",
                            "api_key_env": "TEST_OPENAI_API_KEY",
                            "model": "gpt-4.1",
                        },
                        "glm-main": {
                            "provider": "zhipu",
                            "base_url": "https://glm.example/v1",
                            "api_key_env": "TEST_GLM_API_KEY",
                            "model": "glm-4.5",
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr("agent.core.llm_profiles.LLM_PROFILES_PATH", profile_file)
        monkeypatch.setenv("TEST_OPENAI_API_KEY", "openai-secret")
        monkeypatch.setenv("TEST_GLM_API_KEY", "glm-secret")

        profile = load_llm_profile("glm-main")

        assert profile.name == "glm-main"
        assert profile.provider == "zhipu"
        assert profile.base_url == "https://glm.example/v1"
        assert profile.api_key == "glm-secret"
        assert profile.model == "glm-4.5"
    finally:
        cleanup_test_dir(tmp_dir)


def test_load_llm_profile_requires_api_key_env(monkeypatch):
    tmp_dir = make_test_dir("llm-profile-missing-key")
    try:
        config_dir = tmp_dir / "config"
        config_dir.mkdir(parents=True)
        profile_file = config_dir / "llm_profiles.json"
        profile_file.write_text(
            json.dumps(
                {
                    "default": "openai-main",
                    "profiles": {
                        "openai-main": {
                            "provider": "openai",
                            "base_url": "https://api.openai.com/v1",
                            "api_key_env": "MISSING_OPENAI_API_KEY",
                            "model": "gpt-4.1",
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr("agent.core.llm_profiles.LLM_PROFILES_PATH", profile_file)
        monkeypatch.delenv("MISSING_OPENAI_API_KEY", raising=False)

        with pytest.raises(ValueError, match="MISSING_OPENAI_API_KEY"):
            load_llm_profile()
    finally:
        cleanup_test_dir(tmp_dir)
