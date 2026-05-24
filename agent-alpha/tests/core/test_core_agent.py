from pathlib import Path
import sys
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from tests.conftest import cleanup_test_dir, make_test_dir
from agent.core.agent_runtime import AgentRuntime


def test_agent_runtime_loads_prompt_docs_from_workspace_root_only():
    tmp_dir = make_test_dir("core-agent")
    try:
        workspace_root = tmp_dir / "workspace"
        nested = workspace_root / "nested"
        nested.mkdir(parents=True)
        (workspace_root / "AGENTS.md").write_text("Use the private rulebook.", encoding="utf-8")
        (workspace_root / "SOUL.md").write_text("You are a patient planner.", encoding="utf-8")
        (nested / "AGENTS.md").write_text("This should not be loaded.", encoding="utf-8")

        with patch("agent.core.agent_runtime.ToolLoader.load_all", lambda self: []), patch(
            "agent.core.agent_runtime.LLMClient.from_profile",
            side_effect=lambda profile_name=None: object(),
        ):
            agent = AgentRuntime(
                workspace_root=str(workspace_root),
                logs_dir=str(tmp_dir / "logs"),
            )

        assert agent.workspace_root == workspace_root.resolve()
        assert not hasattr(agent, "workspaces")
        assert "Use the private rulebook." in agent.system_prompt
        assert "You are a patient planner." in agent.system_prompt
        assert "This should not be loaded." not in agent.system_prompt
    finally:
        cleanup_test_dir(tmp_dir)


def test_agent_runtime_exposes_log_payload_without_owning_log_files():
    tmp_dir = make_test_dir("core-agent-log")
    try:
        workspace_root = tmp_dir / "workspace"
        workspace_root.mkdir(parents=True)

        with patch(
            "agent.core.agent_runtime.ToolLoader.load_all",
            lambda self: [],
        ), patch(
            "agent.core.agent_runtime.LLMClient.from_profile",
            side_effect=lambda profile_name=None: object(),
        ):
            agent = AgentRuntime(workspace_root=str(workspace_root))

        agent.history = [{"role": "user", "content": "hello"}]
        payload = agent.get_session_log_data()

        assert payload["history"] == [{"role": "user", "content": "hello"}]
        assert payload["available_tools"] == 0
        assert "system_prompt" in payload
        assert payload["workspace"] == str(workspace_root.resolve())
        assert not hasattr(agent, "session_id")
        assert not hasattr(agent, "logs_dir")
        assert not hasattr(agent, "input_dir")
    finally:
        cleanup_test_dir(tmp_dir)


def test_agent_runtime_uses_selected_llm_profile():
    tmp_dir = make_test_dir("core-agent-profile")
    try:
        workspace_root = tmp_dir / "workspace"
        workspace_root.mkdir(parents=True)
        captured = {}

        class DummyLLM:
            pass

        def fake_from_profile(profile_name=None):
            captured["profile_name"] = profile_name
            return DummyLLM()

        with patch("agent.core.agent_runtime.ToolLoader.load_all",
            lambda self: [],
        ), patch(
            "agent.core.agent_runtime.LLMClient.from_profile",
            side_effect=fake_from_profile,
        ):
            agent = AgentRuntime(workspace_root=str(workspace_root), llm_profile_name="kimi-fast")

        assert captured["profile_name"] == "kimi-fast"
        assert isinstance(agent.llm, DummyLLM)
    finally:
        cleanup_test_dir(tmp_dir)


def test_agent_runtime_handle_delegates_to_agent_loop():
    tmp_dir = make_test_dir("core-agent-handle")
    try:
        workspace_root = tmp_dir / "workspace"
        workspace_root.mkdir(parents=True)

        class DummyLoop:
            def __init__(self, **kwargs):
                self.kwargs = kwargs
                self.history = kwargs["history"]

            def run(self, user_input):
                self.history.append({"role": "user", "content": user_input})
                self.history.append({"role": "assistant", "content": f"handled:{user_input}"})
                return f"handled:{user_input}"

        with patch("agent.core.agent_runtime.ToolLoader.load_all", lambda self: []), patch(
            "agent.core.agent_runtime.LLMClient.from_profile",
            side_effect=lambda profile_name=None: object(),
        ), patch(
            "agent.core.agent_runtime.AgentLoop",
            DummyLoop,
        ):
            agent = AgentRuntime(workspace_root=str(workspace_root))
            response = agent.handle("hello runtime")

        assert response.content == "handled:hello runtime"
        assert response.session_id == "runtime:local"
        assert agent.history[0] == {"role": "user", "content": "hello runtime"}
        assert agent.history[-1] == {"role": "assistant", "content": "handled:hello runtime"}
    finally:
        cleanup_test_dir(tmp_dir)
