from pathlib import Path
import sys
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from tests.conftest import cleanup_test_dir, make_test_dir
from agent.core.core_agent import Agent


def test_agent_ensures_workspace_dirs_and_loads_prompt_docs():
    tmp_dir = make_test_dir("core-agent")
    try:
        workspace_root = tmp_dir / "workspace"
        input_dir = workspace_root / "input"
        input_dir.mkdir(parents=True)
        (input_dir / "AGENTS.md").write_text("Use the session rulebook.", encoding="utf-8")
        (input_dir / "SOUL.md").write_text("You are a patient planner.", encoding="utf-8")

        with patch("agent.core.core_agent.ToolLoader.load_all", lambda self: []), patch(
            "agent.core.core_agent.LLMClient.from_profile",
            side_effect=lambda profile_name=None: object(),
        ):
            agent = Agent(workspace_root=str(workspace_root), logs_dir=str(tmp_dir / "logs"))

        assert agent.workspace_root == workspace_root.resolve()
        assert agent.input_dir == (workspace_root / "input").resolve()
        assert agent.output_dir == (workspace_root / "output").resolve()
        assert agent.temp_dir == (workspace_root / "temp").resolve()
        assert agent.output_dir.exists()
        assert agent.temp_dir.exists()
        assert "Use the session rulebook." in agent.system_prompt
        assert "You are a patient planner." in agent.system_prompt
    finally:
        cleanup_test_dir(tmp_dir)


def test_agent_exposes_log_payload_without_owning_log_files():
    tmp_dir = make_test_dir("core-agent-log")
    try:
        workspace_root = tmp_dir / "workspace"

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
        assert not hasattr(agent, "session_id")
        assert not hasattr(agent, "logs_dir")
    finally:
        cleanup_test_dir(tmp_dir)


def test_agent_uses_selected_llm_profile():
    tmp_dir = make_test_dir("core-agent-profile")
    try:
        workspace_root = tmp_dir / "workspace"
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
