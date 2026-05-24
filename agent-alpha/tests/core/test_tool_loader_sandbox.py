from pathlib import Path
import sys
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from agent.core.tool_loader import ToolLoader


def test_tool_loader_denies_file_operation_outside_allowed_roots():
    loader = ToolLoader(
        project_root=Path("D:/demo/agent-alpha"),
        enable_permissions=False,
        workspace_root=Path("D:/demo/agent-alpha/workspace"),
    )
    loader.tool_executors["write"] = lambda **kwargs: {"success": True, "details": kwargs}

    result = loader.execute_tool("write", {"file_path": "D:/outside/data.txt", "content": "x"})

    assert result["error"] == "Sandbox denied"
    assert result["tool"] == "write"


def test_tool_loader_asks_user_for_project_write_and_allows_once():
    loader = ToolLoader(
        project_root=Path("D:/demo/agent-alpha"),
        enable_permissions=True,
        workspace_root=Path("D:/demo/agent-alpha/workspace"),
    )
    loader.tool_executors["write"] = lambda **kwargs: {"success": True, "details": kwargs}

    with patch.object(loader.permission_manager, "ask_user", return_value=True):
        result = loader.execute_tool("write", {"file_path": "D:/demo/agent-alpha/README.md", "content": "x"})

    assert result["success"] is True
    assert result["details"]["file_path"] == "D:/demo/agent-alpha/README.md"


def test_tool_loader_returns_retry_context_when_user_supplies_extra_instruction():
    loader = ToolLoader(
        project_root=Path("D:/demo/agent-alpha"),
        enable_permissions=True,
        workspace_root=Path("D:/demo/agent-alpha/workspace"),
    )

    with patch.object(
        loader.permission_manager,
        "ask_user",
        return_value={"retry_with_context": "请只修改 README 的说明部分"},
    ):
        result = loader.execute_tool("write", {"file_path": "D:/demo/agent-alpha/README.md", "content": "x"})

    assert result["retry_with_context"] == "请只修改 README 的说明部分"
    assert result["tool"] == "write"
