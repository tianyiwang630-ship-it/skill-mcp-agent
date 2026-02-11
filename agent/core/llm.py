from openai import OpenAI
from typing import List, Dict, Any, Optional

from agent.core.config import LLM_MAX_TOKENS, LLM_BASE_URL, LLM_API_KEY, LLM_MODEL_NAME

class LLMClient:
    def __init__(self, model_name: str = LLM_MODEL_NAME):
        self.client = OpenAI(
            base_url=LLM_BASE_URL,
            api_key=LLM_API_KEY
        )
        self.model_name = model_name

    def generate(self, prompt: str, max_tokens: int = LLM_MAX_TOKENS) -> str:
        """
        生成响应

        Args:
            prompt: 输入提示词
            max_tokens: 最大token数（默认100000）

        Returns:
            生成的文本内容
        """
        completion = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_tokens
        )
        return completion.choices[0].message.content

    def generate_with_tools(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: int = LLM_MAX_TOKENS
    ) -> Any:
        """
        使用工具进行生成（支持 function calling）

        Args:
            messages: 对话消息列表
            tools: 工具列表（OpenAI format）
            max_tokens: 最大 token 数

        Returns:
            OpenAI 响应对象
        """
        kwargs = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": max_tokens
        }

        # 如果提供了工具，添加到参数中
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"  # 让模型自动决定是否使用工具

        completion = self.client.chat.completions.create(**kwargs)
        return completion