"""
Core Agent implementation.
"""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

try:
    import msvcrt

    HAS_MSVCRT = True
except ImportError:  # pragma: no cover - platform specific
    HAS_MSVCRT = False

from agent.core.agent_loop import AgentLoop
from agent.core.config import KEEP_RECENT_TURNS, MAX_CONTEXT_TOKENS, MAX_TOOL_RESULT_CHARS
from agent.core.context_manager import ContextManager
from agent.core.llm import LLMClient
from agent.core.prompt_docs_loader import load_session_prompt_documents
from agent.core.session_paths import SessionPaths, create_session_paths
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
        task_id: str | None = None,
        llm_profile_name: str | None = None,
    ):
        self.workspace_root = Path(workspace_root).resolve() if workspace_root else PROJECT_ROOT.resolve()
        self.task_id = task_id
        self.llm_profile_name = llm_profile_name
        self.session_id = self._generate_session_id()
        self.session_start_time = datetime.now()

        self.session_paths: SessionPaths = create_session_paths(
            workspace_root=self.workspace_root,
            session_id=self.session_id,
        )
        self.session_root = self.session_paths.session_root
        self.input_dir = self.session_paths.input_dir
        self.output_dir = self.session_paths.output_dir
        self.temp_dir = self.session_paths.temp_dir
        self.logs_dir = self.session_paths.logs_dir

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
            fetch.temp_dir = self.temp_dir

        self.prompt_documents = load_session_prompt_documents(self.input_dir)
        self.system_prompt = self._build_system_prompt()

        self.context_manager = ContextManager(
            llm=self.llm,
            tools=self.tools,
            system_prompt=self.system_prompt,
            max_context_tokens=MAX_CONTEXT_TOKENS,
            keep_recent_turns=KEEP_RECENT_TURNS,
        )

    def _generate_session_id(self) -> str:
        import uuid

        return uuid.uuid4().hex[:6]

    def _build_system_prompt(self) -> str:
        return build_system_prompt(
            workspace_root=self.workspace_root,
            session_root=self.session_root,
            input_dir=self.input_dir,
            output_dir=self.output_dir,
            temp_dir=self.temp_dir,
            logs_dir=self.logs_dir,
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
        context = {
            "system_prompt": self.system_prompt,
            "available_tools": len(self.tools),
            "history": self.history,
        }
        return json.dumps(context, ensure_ascii=False, indent=2)

    def save_context(self, filepath: str):
        Path(filepath).write_text(self.get_context_json(), encoding="utf-8")
        print(f"Saved context to: {filepath}")

    def reset(self):
        self.history = []
        print("Session history cleared.")

    def save_session_log(self):
        if not self.history:
            print("No session history to save.")
            return

        session_end_time = datetime.now()
        timestamp = self.session_start_time.strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{timestamp}_session_{self.session_id}.json"
        filepath = self.logs_dir / filename

        log_data = {
            "session_id": self.session_id,
            "start_time": self.session_start_time.isoformat(),
            "end_time": session_end_time.isoformat(),
            "duration_seconds": (session_end_time - self.session_start_time).total_seconds(),
            "total_turns": len([msg for msg in self.history if msg["role"] == "user"]),
            "history": self.history,
        }

        try:
            filepath.write_text(json.dumps(log_data, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Saved session log: {filepath}")
            self._append_session_index(filepath)
        except Exception as exc:  # pragma: no cover - logging fallback
            print(f"Failed to save session log: {exc}")

    def _append_session_index(self, log_filepath: Path):
        try:
            index_file = self.workspace_root / "sessions" / "index.md"
            index_file.parent.mkdir(parents=True, exist_ok=True)

            user_turns = len([message for message in self.history if message["role"] == "user"])
            first_msg = next((m["content"][:100] for m in self.history if m["role"] == "user"), "")
            first_msg = first_msg.replace("\n", " ").replace("|", "/")
            has_temp = self.temp_dir.exists() and any(self.temp_dir.iterdir())

            if not index_file.exists():
                header = "# Session Index\n\n"
                header += "| Session ID | Started | User Turns | Temp Dir | Log File | First User Message |\n"
                header += "|---|---|---:|---|---|---|\n"
                index_file.write_text(header, encoding="utf-8")

            time_str = self.session_start_time.strftime("%m-%d %H:%M")
            temp_str = str(self.temp_dir.relative_to(self.workspace_root)) if has_temp else "-"
            log_str = str(log_filepath.relative_to(self.workspace_root))
            line = f"| {self.session_id} | {time_str} | {user_turns} | {temp_str} | {log_str} | {first_msg} |\n"
            with open(index_file, "a", encoding="utf-8") as handle:
                handle.write(line)
        except Exception as exc:  # pragma: no cover - logging fallback
            print(f"Failed to update session index: {exc}")
