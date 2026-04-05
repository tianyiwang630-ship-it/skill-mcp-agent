from pathlib import Path
import sys
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from agent.core.command_path_extractor import classify_bash_command
from agent.core.sandbox_guard import SandboxGuard
from agent.core.tool_loader import ToolLoader


def _guard() -> SandboxGuard:
    return SandboxGuard(
        project_root=Path("D:/demo/agent-alpha"),
        workspaces=[Path("D:/demo/agent-alpha/workspace")],
    )


def test_classify_python_script_run():
    assert classify_bash_command('python "D:/demo/agent-alpha/workspace/job.py"') == "script_run"


def test_bash_allows_python_script_inside_project():
    result = _guard().check_tool_call("bash", {"command": 'python "D:/demo/agent-alpha/scripts/run.py"'})

    assert result.decision == "allow"
    assert result.reason.startswith("Script execution is allowed")


def test_bash_denies_python_script_outside_project():
    result = _guard().check_tool_call("bash", {"command": 'python "D:/other/place/run.py"'})

    assert result.decision == "deny"
    assert "agent workspace or the agent-alpha project" in result.reason


def test_bash_asks_for_package_install():
    result = _guard().check_tool_call("bash", {"command": "npm install playwright"})

    assert result.decision == "ask"
    assert result.action == "write"


def test_bash_asks_for_package_uninstall():
    result = _guard().check_tool_call("bash", {"command": "npm uninstall playwright"})

    assert result.decision == "ask"
    assert result.action == "write"


def test_bash_allows_project_command():
    result = _guard().check_tool_call("bash", {"command": "python -m pytest"})

    assert result.decision == "allow"
    assert result.action == "read"


def test_bash_allows_git_apply():
    result = _guard().check_tool_call("bash", {"command": "git apply D:/demo/agent-alpha/workspace/fix.patch"})

    assert result.decision == "allow"


def test_bash_asks_for_bulk_git_restore():
    result = _guard().check_tool_call("bash", {"command": "git restore ."})

    assert result.decision == "ask"
    assert result.action == "write"


def test_bash_allows_git_checkout_single_file_inside_workspace():
    result = _guard().check_tool_call("bash", {"command": "git checkout -- D:/demo/agent-alpha/workspace/app.py"})

    assert result.decision == "allow"
    assert result.action == "write"


def test_bash_denies_git_clean_force():
    result = _guard().check_tool_call("bash", {"command": "git clean -fd"})

    assert result.decision == "deny"


def test_bash_denies_unparseable_mutation_and_returns_guidance():
    result = _guard().check_tool_call("bash", {"command": 'echo hello > "$TARGET_FILE"'})

    assert result.decision == "deny"
    assert result.guidance is not None
    assert "mkdir path" in result.guidance


def test_bash_allows_simple_mutation_inside_workspace():
    result = _guard().check_tool_call("bash", {"command": "mkdir D:/demo/agent-alpha/workspace/output"})

    assert result.decision == "allow"
    assert result.action == "write"


def test_tool_loader_returns_guidance_for_denied_bash():
    loader = ToolLoader(
        project_root=Path("D:/demo/agent-alpha"),
        enable_permissions=False,
        workspaces=[Path("D:/demo/agent-alpha/workspace")],
    )

    result = loader.execute_tool("bash", {"command": 'echo hello > "$TARGET_FILE"'})

    assert result["error"] == "Sandbox denied"
    assert "guidance" in result


def test_tool_loader_allows_project_command_bash_without_prompt():
    loader = ToolLoader(
        project_root=Path("D:/demo/agent-alpha"),
        enable_permissions=True,
        workspaces=[Path("D:/demo/agent-alpha/workspace")],
    )
    loader.tool_executors["bash"] = lambda **kwargs: {"success": True, "details": kwargs}

    with patch.object(loader.permission_manager, "ask_user", side_effect=AssertionError("should not prompt")):
        result = loader.execute_tool("bash", {"command": "python -m compileall agent"})

    assert result["success"] is True
    assert result["details"]["command"] == "python -m compileall agent"
