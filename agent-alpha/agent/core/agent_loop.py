"""
Agent loop extraction for multi-turn tool execution.
"""

from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


class AgentLoop:
    """Run the agent message loop while reusing the caller's history list."""

    def __init__(
        self,
        *,
        llm,
        tools: List[Dict[str, Any]],
        tool_loader,
        history: List[Dict[str, Any]],
        system_prompt: str,
        max_turns: int,
        max_tool_result_chars: int = 12000,
        interrupt_event: Optional[threading.Event] = None,
        start_interrupt_listener: Optional[Callable[[], Any]] = None,
    ):
        self.llm = llm
        self.tools = tools
        self.tool_loader = tool_loader
        self.history = history
        self.system_prompt = system_prompt
        self.max_turns = max_turns
        self.max_tool_result_chars = max_tool_result_chars
        self._interrupted = interrupt_event or threading.Event()
        self._start_interrupt_listener = start_interrupt_listener

    def run(self, user_input: str) -> str:
        """Execute the multi-turn loop for one user input."""
        self.history.append({"role": "user", "content": user_input})

        self._interrupted.clear()
        if self._start_interrupt_listener:
            self._start_interrupt_listener()

        try:
            for _ in range(self.max_turns):
                if self._interrupted.is_set():
                    break

                messages = self._build_messages()
                message = self._call_llm_interruptible(messages)
                if message is None:
                    break

                if getattr(message, "tool_calls", None):
                    self._handle_tool_calls(message)
                    if self._interrupted.is_set():
                        break
                    continue

                self.history.append({"role": "assistant", "content": message.content})
                return message.content

            if self._interrupted.is_set():
                return "[用户中断] 已停止当前任务。"
            return "抱歉，任务太复杂，已达到最大处理轮次。"
        finally:
            self._interrupted.set()

    def _call_llm(self, messages: List[Dict[str, Any]]) -> Any:
        response = self.llm.generate_with_tools(messages=messages, tools=self.tools)
        message = response.choices[0].message

        if hasattr(message, "tool_calls") and message.tool_calls:
            debug_mode = os.environ.get("DEBUG_AGENT", "0") == "1"
            if debug_mode:
                debug_file = Path("workspace/temp/last_llm_response.json")
                debug_file.parent.mkdir(parents=True, exist_ok=True)
                debug_data = {
                    "content": message.content,
                    "tool_calls": [
                        {
                            "name": tc.function.name,
                            "arguments_raw": tc.function.arguments,
                        }
                        for tc in message.tool_calls
                    ],
                }
                debug_file.write_text(json.dumps(debug_data, ensure_ascii=False, indent=2), encoding="utf-8")

        return message

    def _call_llm_interruptible(self, messages: List[Dict[str, Any]]) -> Any:
        result: List[Any] = [None]
        error: List[Optional[Exception]] = [None]

        def call():
            try:
                result[0] = self._call_llm(messages)
            except Exception as exc:  # pragma: no cover - passthrough branch
                error[0] = exc

        thread = threading.Thread(target=call)
        thread.start()

        while thread.is_alive():
            thread.join(timeout=0.1)
            if self._interrupted.is_set():
                return None

        if error[0]:
            raise error[0]
        return result[0]

    def _handle_tool_calls(self, message) -> None:
        self.history.append(
            {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in message.tool_calls
                ],
            }
        )

        for tool_call in message.tool_calls:
            if self._interrupted.is_set():
                self.history.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": "[用户中断] 此工具调用未执行",
                    }
                )
                continue

            result = self._execute_single_tool(tool_call)

            if isinstance(result, dict) and "retry_with_context" in result:
                extra_instruction = result["retry_with_context"]
                if self.history and self.history[-1]["role"] == "assistant":
                    self.history.pop()
                self.history.append({"role": "user", "content": f"[补充说明] {extra_instruction}"})
                break

            result_str = json.dumps(result, ensure_ascii=False) if isinstance(result, dict) else str(result)
            result_str = re.sub(r"\x1b\[[0-9;]*m", "", result_str)

            if len(result_str) > self.max_tool_result_chars:
                result_str = (
                    result_str[: self.max_tool_result_chars]
                    + f"\n\n... (已截断，原始 {len(result_str)} 字符)"
                )

            self.history.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result_str,
                }
            )

    def _execute_single_tool(self, tool_call) -> Any:
        tool_name = tool_call.function.name
        raw_arguments = tool_call.function.arguments

        try:
            arguments = json.loads(raw_arguments)
        except json.JSONDecodeError:
            try:
                arguments = json.loads(raw_arguments.replace("'", '"'))
            except Exception:
                arguments = {}

        return self.tool_loader.execute_tool(tool_name, arguments)

    def _build_messages(self) -> List[Dict[str, Any]]:
        return [{"role": "system", "content": self.system_prompt}, *self.history]
