from typing import Any, Optional

from openai import OpenAI

from agent.api.llm_profiles import LLMProfile, load_llm_profile
from agent.core.config import LLM_MAX_TOKENS


class LLMClient:
    def __init__(self, profile: LLMProfile):
        self.profile = profile
        self.client = OpenAI(base_url=profile.base_url, api_key=profile.api_key)
        self.model_name = profile.model

    @classmethod
    def from_profile(cls, profile_name: str | None = None) -> "LLMClient":
        return cls(load_llm_profile(profile_name))

    def generate(self, prompt: str, max_tokens: int = LLM_MAX_TOKENS) -> str:
        completion = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
        )
        return completion.choices[0].message.content

    def generate_with_tools(
        self,
        messages: list[dict[str, str]],
        tools: Optional[list[dict[str, Any]]] = None,
        max_tokens: int = LLM_MAX_TOKENS,
    ) -> Any:
        kwargs = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": max_tokens,
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        return self.client.chat.completions.create(**kwargs)
