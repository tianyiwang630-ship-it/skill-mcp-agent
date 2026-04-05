import sys
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from tests.conftest import cleanup_test_dir, make_test_dir
from agent.core.tool_loader import ToolLoader


def test_tool_loader_registers_single_load_skill_tool():
    tmp_dir = make_test_dir("tool-loader")
    try:
        project_root = tmp_dir / "project"
        skills_dir = project_root / "skills" / "pdf"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text(
            """---
name: pdf
description: Process PDF files
---
Use OCR when needed.
""",
            encoding="utf-8",
        )

        with patch.object(ToolLoader, "_load_mcp_tools", lambda self: None), patch.object(
            ToolLoader, "_load_builtin_tools", lambda self: None
        ):
            loader = ToolLoader(project_root=project_root, enable_permissions=False)
            tools = loader.load_all()
            tool_names = [tool["function"]["name"] for tool in tools]

            assert "load_skill" in tool_names
            assert all(not name.startswith("skill__") for name in tool_names)

            result = loader.execute_tool("load_skill", {"name": "pdf"})
            assert result == '<skill name="pdf">\nUse OCR when needed.\n</skill>'
    finally:
        cleanup_test_dir(tmp_dir)


def test_tool_loader_clears_runtime_state_on_reload():
    tmp_dir = make_test_dir("tool-loader")
    try:
        project_root = tmp_dir / "project"
        (project_root / "skills" / "pdf").mkdir(parents=True)
        (project_root / "skills" / "pdf" / "SKILL.md").write_text(
            """---
name: pdf
description: Process PDF files
---
Use OCR when needed.
""",
            encoding="utf-8",
        )

        def fake_builtin_loader(self):
            self.tools.append({"type": "function", "function": {"name": "fake_builtin"}})
            self.tool_executors["fake_builtin"] = lambda: "ok"
            self.tool_instances["fake_builtin"] = object()

        loader = ToolLoader(project_root=project_root, enable_permissions=False)

        with patch.object(ToolLoader, "_load_mcp_tools", lambda self: None), patch.object(
            ToolLoader, "_load_builtin_tools", fake_builtin_loader
        ):
            loader.load_all()

        assert "fake_builtin" in loader.tool_instances

        with patch.object(ToolLoader, "_load_mcp_tools", lambda self: None), patch.object(
            ToolLoader, "_load_builtin_tools", lambda self: None
        ):
            loader.load_all()

        assert loader.tool_instances == {}
    finally:
        cleanup_test_dir(tmp_dir)
