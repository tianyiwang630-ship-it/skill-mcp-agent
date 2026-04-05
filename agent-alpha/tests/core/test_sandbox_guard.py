from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from agent.core.sandbox_guard import SandboxGuard


def test_sandbox_guard_allows_read_inside_workspace():
    workspaces = [Path("D:/demo/agent-alpha/sessions/abc123")]
    project_root = Path("D:/demo/agent-alpha")
    guard = SandboxGuard(project_root=project_root, workspaces=workspaces)

    result = guard.check_tool_call("read", {"file_path": "D:/demo/agent-alpha/sessions/abc123/note.txt"})

    assert result.decision == "allow"
    assert result.action == "read"
    assert result.zone == "workspace"


def test_sandbox_guard_asks_for_write_inside_project_but_outside_workspace():
    workspaces = [Path("D:/demo/agent-alpha/sessions/abc123")]
    project_root = Path("D:/demo/agent-alpha")
    guard = SandboxGuard(project_root=project_root, workspaces=workspaces)

    result = guard.check_tool_call("write", {"file_path": "D:/demo/agent-alpha/agent/core/config.py"})

    assert result.decision == "ask"
    assert result.action == "write"
    assert result.zone == "project"


def test_sandbox_guard_denies_read_outside_project_and_workspace():
    workspaces = [Path("D:/demo/agent-alpha/sessions/abc123")]
    project_root = Path("D:/demo/agent-alpha")
    guard = SandboxGuard(project_root=project_root, workspaces=workspaces)

    result = guard.check_tool_call("read", {"file_path": "D:/other/place/secret.txt"})

    assert result.decision == "deny"
    assert result.zone == "outside"


def test_sandbox_guard_denies_when_file_path_is_missing():
    workspaces = [Path("D:/demo/agent-alpha/sessions/abc123")]
    project_root = Path("D:/demo/agent-alpha")
    guard = SandboxGuard(project_root=project_root, workspaces=workspaces)

    result = guard.check_tool_call("write", {})

    assert result.decision == "deny"
    assert result.zone == "unknown"
