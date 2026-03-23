"""
Core Agent implementation.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Sequence

try:
    import msvcrt

    HAS_MSVCRT = True
except ImportError:  # pragma: no cover - platform specific
    HAS_MSVCRT = False

from agent.core.agent_loop import AgentLoop
from agent.core.config import KEEP_RECENT_TURNS, MAX_CONTEXT_TOKENS, MAX_TOOL_RESULT_CHARS
from agent.core.context_manager import ContextManager
from agent.core.llm import LLMClient
from agent.core.prompt_docs_loader import load_workspace_prompt_documents
from agent.core.skill_loader import SkillLoader
from agent.core.system_prompt_builder import build_system_prompt
from agent.core.tool_loader import ToolLoader


PROJECT_ROOT = Path(__file__).parent.parent.parent


class Agent:
    """Reusable agent instance with workspace-scoped session state."""

    def __init__(
        self,
        max_turns: int = 5000,
        workspace_root: str | None = None,
        workspaces: Sequence[str | Path] | None = None,
        logs_dir: str | None = None,
        task_id: str | None = None,
        llm_profile_name: str | None = None,
    ):
        self.workspaces = self._normalize_workspaces(workspace_root, workspaces)
        self.workspace_root = self.workspaces[0]
        self.additional_workspaces = self.workspaces[1:]
        self.runtime_logs_dir = Path(logs_dir).resolve() if logs_dir else None
        self.task_id = task_id
        self.llm_profile_name = llm_profile_name

        for workspace in self.workspaces:
            workspace.mkdir(parents=True, exist_ok=True)

        self.llm = LLMClient.from_profile(llm_profile_name)
        self.skill_loader = SkillLoader(PROJECT_ROOT / "skills")
        self.tool_loader = ToolLoader(project_root=PROJECT_ROOT, skill_loader=self.skill_loader)
        self.max_turns = max_turns
        self.history: List[Dict[str, Any]] = []
        self._interrupted = threading.Event()

        print("Loading Agent...")
        self.tools = self.tool_loader.load_all()

        fetch = self.tool_loader.tool_instances.get("fetch")
        if fetch:
            fetch.temp_dir = self.workspace_root

        self.prompt_documents = load_workspace_prompt_documents(self.workspaces)
        self.system_prompt = self._build_system_prompt()

        self.context_manager = ContextManager(
            llm=self.llm,
            tools=self.tools,
            system_prompt=self.system_prompt,
            max_context_tokens=MAX_CONTEXT_TOKENS,
            keep_recent_turns=KEEP_RECENT_TURNS,
        )

    def _normalize_workspaces(
        self,
        workspace_root: str | None,
        workspaces: Sequence[str | Path] | None,
    ) -> List[Path]:
        if workspaces:
            resolved = [Path(workspace).resolve() for workspace in workspaces]
        else:
            default_workspace = Path(workspace_root).resolve() if workspace_root else PROJECT_ROOT.resolve()
            resolved = [default_workspace]

        if not resolved:
            raise ValueError("Agent requires at least one workspace")
        return resolved

    def _build_system_prompt(self) -> str:
        return build_system_prompt(
            private_workspace=self.workspace_root,
            additional_workspaces=self.additional_workspaces,
            logs_dir=self.runtime_logs_dir,
            skills_dir=PROJECT_ROOT / "skills",
            mcp_servers_dir=PROJECT_ROOT / "mcp-servers",
            mcp_registry_path=PROJECT_ROOT / "mcp-servers" / "registry.json",
            task_id=self.task_id,
            skill_summaries=self.skill_loader.get_summaries(),
            prompt_documents=self.prompt_documents,
        )

    def run(self, user_input: str) -> str:
        if self.context_manager.should_compress(self.history):
            self.history = self.context_manager.compress_history(self.history)

        loop = AgentLoop(
            llm=self.llm,
            tools=self.tools,
            tool_loader=self.tool_loader,
            history=self.history,
            system_prompt=self.system_prompt,
            max_turns=self.max_turns,
            max_tool_result_chars=MAX_TOOL_RESULT_CHARS,
            interrupt_event=self._interrupted,
            start_interrupt_listener=self._start_esc_listener,
        )
        return loop.run(user_input)

    def _start_esc_listener(self):
        if not HAS_MSVCRT:
            return None

        self._interrupted.clear()
        last_esc = [0.0]

        def listener():
            while not self._interrupted.is_set():
                if msvcrt.kbhit():
                    key = msvcrt.getch()
                    if key == b"\x1b":
                        now = time.time()
                        if now - last_esc[0] < 1.0:
                            self._interrupted.set()
                            print("\n\nInterrupted by ESC.")
                            return
                        last_esc[0] = now
                time.sleep(0.05)

        thread = threading.Thread(target=listener, daemon=True)
        thread.start()
        return thread

    def get_context_json(self) -> str:
        context = self.get_session_log_data()
        return json.dumps(context, ensure_ascii=False, indent=2)

    def get_session_log_data(self) -> Dict[str, Any]:
        return {
            "system_prompt": self.system_prompt,
            "available_tools": len(self.tools),
            "workspaces": [str(path) for path in self.workspaces],
            "history": self.history,
        }

    def save_context(self, filepath: str):
        Path(filepath).write_text(self.get_context_json(), encoding="utf-8")
        print(f"Saved context to: {filepath}")

    def reset(self):
        self.history = []
        print("Session history cleared.")
