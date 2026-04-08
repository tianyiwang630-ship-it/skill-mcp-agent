from pathlib import Path
import sys
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from tests.conftest import cleanup_test_dir, make_test_dir
from agent.core.role_config import RoleConfig
from agent.core.tool_loader import ToolLoader


def test_tool_loader_resolves_tools_with_role_policy():
    tmp_dir = make_test_dir("tool-loader-policy")
    try:
        project_root = tmp_dir / "project"
        project_root.mkdir(parents=True)

        def fake_loaders(self):
            self.tools.extend(
                [
                    {"type": "function", "function": {"name": "read"}},
                    {"type": "function", "function": {"name": "write"}},
                    {"type": "function", "function": {"name": "bash"}},
                ]
            )
            self.tool_executors["read"] = lambda **kwargs: kwargs
            self.tool_executors["write"] = lambda **kwargs: kwargs
            self.tool_executors["bash"] = lambda **kwargs: kwargs

        loader = ToolLoader(project_root=project_root, enable_permissions=False)
        with patch.object(ToolLoader, "_load_mcp_tools", lambda self: None), patch.object(
            ToolLoader, "_load_skills", lambda self: None
        ), patch.object(
            ToolLoader, "_load_builtin_tools", fake_loaders
        ):
            loader.load_all()

        resolved = loader.resolve_tools(
            RoleConfig(
                name="worker",
                allowed_tools=["read", "write", "bash"],
                denied_tools=["bash"],
            )
        )
        tool_names = [tool["function"]["name"] for tool in resolved]

        assert tool_names == ["read", "write"]
    finally:
        cleanup_test_dir(tmp_dir)
