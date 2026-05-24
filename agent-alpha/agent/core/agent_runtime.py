"""
Primary agent runtime entrypoint.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Dict, List

try:
    import msvcrt

    HAS_MSVCRT = True
except ImportError:  # pragma: no cover - platform specific
    HAS_MSVCRT = False

from agent.api.llm import LLMClient
from agent.core.agent_loop import AgentLoop
from agent.core.config import KEEP_RECENT_TURNS, MAX_CONTEXT_TOKENS, MAX_TOOL_RESULT_CHARS
from agent.core.context_manager import ContextManager
from agent.core.prompt_docs_loader import load_workspace_prompt_documents
from agent.core.role_config import RoleConfig
from agent.core.runtime_types import RuntimeRequest, RuntimeResponse
from agent.core.skill_loader import SkillLoader
from agent.core.system_prompt_builder import build_system_prompt
from agent.core.tool_loader import ToolLoader


PROJECT_ROOT = Path(__file__).parent.parent.parent


class AgentRuntime:
    """Reusable runtime for a single agent instance."""

    def __init__(
        self,
        max_turns: int = 5000,
        workspace_root: str | None = None,
        logs_dir: str | None = None,
        task_id: str | None = None,
        llm_profile_name: str | None = None,
        role_config: RoleConfig | None = None,
    ):
        self.workspace_root = Path(workspace_root).resolve() if workspace_root else PROJECT_ROOT.resolve()
        self.runtime_logs_dir = Path(logs_dir).resolve() if logs_dir else None
        self.task_id = task_id
        self.llm_profile_name = llm_profile_name
        self.role_config = role_config or RoleConfig()

        self.workspace_root.mkdir(parents=True, exist_ok=True)

        self.llm = LLMClient.from_profile(llm_profile_name)
        self.skill_loader = SkillLoader(PROJECT_ROOT / "skills")
        self.tool_loader = ToolLoader(
            project_root=PROJECT_ROOT,
            skill_loader=self.skill_loader,
            workspace_root=self.workspace_root,
        )
        self.max_turns = max_turns
        self.history: List[Dict[str, Any]] = []
        self._interrupted = threading.Event()

        print("Loading Agent Runtime...")
        self.tool_loader.load_all()
        self.tools = self.tool_loader.resolve_tools(self.role_config)
        self.tool_loader.configure_runtime(self.workspace_root)

        self.prompt_documents = load_workspace_prompt_documents(self.workspace_root)
        self.system_prompt = self._build_system_prompt()

        self.context_manager = ContextManager(
            llm=self.llm,
            tools=self.tools,
            system_prompt=self.system_prompt,
            max_context_tokens=MAX_CONTEXT_TOKENS,
            keep_recent_turns=KEEP_RECENT_TURNS,
        )

    def _build_system_prompt(self) -> str:
        return build_system_prompt(
            workspace_root=self.workspace_root,
            logs_dir=self.runtime_logs_dir,
            skills_dir=PROJECT_ROOT / "skills",
            mcp_servers_dir=PROJECT_ROOT / "mcp-servers",
            mcp_registry_path=PROJECT_ROOT / "mcp-servers" / "registry.json",
            task_id=self.task_id,
            skill_summaries=self.skill_loader.get_summaries(),
            prompt_documents=self.prompt_documents,
        )

    def handle(self, request: str | RuntimeRequest) -> RuntimeResponse:
        runtime_request = request if isinstance(request, RuntimeRequest) else RuntimeRequest(content=request)

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
        result = loop.run(runtime_request.content)
        return RuntimeResponse(
            content=result,
            session_id=runtime_request.session_id,
            metadata={"source": runtime_request.source, **runtime_request.metadata},
        )

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
            "workspace": str(self.workspace_root),
            "history": self.history,
            "role": self.role_config.name,
        }

    def save_context(self, filepath: str):
        Path(filepath).write_text(self.get_context_json(), encoding="utf-8")
        print(f"Saved context to: {filepath}")

    def reset(self):
        self.history = []
        print("Session history cleared.")

    def close(self) -> None:
        mcp_mgr = self.tool_loader.tool_executors.get("_mcp_manager")
        if mcp_mgr:
            try:
                mcp_mgr.close_all()
            except Exception:
                pass
