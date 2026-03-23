from pathlib import Path
import sys
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from tests.conftest import cleanup_test_dir, make_test_dir
from agent.core.core_agent import Agent


def test_agent_loads_prompt_docs_only_from_first_workspace_root():
    tmp_dir = make_test_dir("core-agent")
    try:
        first_workspace = tmp_dir / "workspace-a"
        second_workspace = tmp_dir / "workspace-b"
        first_workspace.mkdir(parents=True)
        second_workspace.mkdir(parents=True)
        (first_workspace / "AGENTS.md").write_text("Use the private rulebook.", encoding="utf-8")
        (first_workspace / "SOUL.md").write_text("You are a patient planner.", encoding="utf-8")
        (second_workspace / "AGENTS.md").write_text("This should not be loaded.", encoding="utf-8")

        with patch("agent.core.core_agent.ToolLoader.load_all", lambda self: []), patch(
            "agent.core.core_agent.LLMClient.from_profile",
            side_effect=lambda profile_name=None: object(),
        ):
            agent = Agent(
                workspaces=[str(first_workspace), str(second_workspace)],
                logs_dir=str(tmp_dir / "logs"),
            )

        assert agent.workspace_root == first_workspace.resolve()
        assert agent.workspaces == [first_workspace.resolve(), second_workspace.resolve()]
        assert "Use the private rulebook." in agent.system_prompt
        assert "You are a patient planner." in agent.system_prompt
        assert "This should not be loaded." not in agent.system_prompt
    finally:
        cleanup_test_dir(tmp_dir)


def test_agent_exposes_log_payload_without_owning_log_files():
    tmp_dir = make_test_dir("core-agent-log")
    try:
        workspace_root = tmp_dir / "workspace"
        workspace_root.mkdir(parents=True)

        with patch(
            "agent.core.core_agent.ToolLoader.load_all",
            lambda self: [],
        ), patch(
            "agent.core.core_agent.LLMClient.from_profile",
            side_effect=lambda profile_name=None: object(),
        ):
            agent = Agent(workspace_root=str(workspace_root))

        agent.history = [{"role": "user", "content": "hello"}]
        payload = agent.get_session_log_data()

        assert payload["history"] == [{"role": "user", "content": "hello"}]
        assert payload["available_tools"] == 0
        assert "system_prompt" in payload
        assert payload["workspaces"] == [str(workspace_root.resolve())]
        assert not hasattr(agent, "session_id")
        assert not hasattr(agent, "logs_dir")
        assert not hasattr(agent, "input_dir")
    finally:
        cleanup_test_dir(tmp_dir)


def test_agent_uses_selected_llm_profile():
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

        with patch("agent.core.core_agent.ToolLoader.load_all",
            lambda self: [],
        ), patch(
            "agent.core.core_agent.LLMClient.from_profile",
            side_effect=fake_from_profile,
        ):
            agent = Agent(workspace_root=str(workspace_root), llm_profile_name="kimi-fast")

        assert captured["profile_name"] == "kimi-fast"
        assert isinstance(agent.llm, DummyLLM)
    finally:
        cleanup_test_dir(tmp_dir)
