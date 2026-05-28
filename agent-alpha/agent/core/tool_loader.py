"""
Central tool registration and execution.

Phase 1 keeps three tool sources:
- MCP tools
- a shared load_skill tool
- builtin local tools
"""

from __future__ import annotations

import importlib
import copy
import json
from pathlib import Path
from typing import Any, Dict, List

from agent.core.bm25 import BM25Index
from agent.core.config import BASH_TOOL_TIMEOUT, DEFAULT_MCP_CATEGORY
from agent.core.role_config import RoleConfig
from agent.core.sandbox_guard import SandboxGuard
from agent.core.skill_loader import SkillLoader


class ToolLoader:
    """Load tool definitions and dispatch tool execution."""

    TOOL_GROUPS = {
        "bash": "shell",
        "read": "filesystem",
        "write": "filesystem",
        "append": "filesystem",
        "edit": "filesystem",
        "glob": "filesystem",
        "grep": "filesystem",
        "fetch": "network",
        "load_skill": "skill",
        "tool_search": "meta",
    }

    BUILTIN_TOOLS = [
        ("agent.tools.bash_tool", "BashTool", {"timeout": BASH_TOOL_TIMEOUT}),
        ("agent.tools.read_tool", "ReadTool", {}),
        ("agent.tools.write_tool", "WriteTool", {}),
        ("agent.tools.append_tool", "AppendTool", {}),
        ("agent.tools.edit_tool", "EditTool", {}),
        ("agent.tools.glob_tool", "GlobTool", {}),
        ("agent.tools.grep_tool", "GrepTool", {}),
        ("agent.tools.fetch_tool", "FetchTool", {}),
    ]

    def __init__(
        self,
        project_root: Path | None = None,
        enable_permissions: bool = True,
        skill_loader: SkillLoader | None = None,
        workspace_root: Path | None = None,
    ):
        if project_root is None:
            current = Path(__file__).parent
            self.project_root = current.parent.parent
        else:
            self.project_root = Path(project_root)

        self.skills_dir = self.project_root / "skills"
        self.skill_loader = skill_loader or SkillLoader(self.skills_dir)
        self.workspace_root = Path(workspace_root).resolve() if workspace_root else self.project_root.resolve()
        self.sandbox_guard = SandboxGuard(project_root=self.project_root, workspace_root=self.workspace_root)

        self.tools: List[Dict[str, Any]] = []
        self.tool_executors: Dict[str, Any] = {}
        self.tool_instances: Dict[str, Any] = {}
        self._catalog_tools: List[Dict[str, Any]] = []
        self._catalog_executors: Dict[str, Any] = {}
        self._catalog_instances: Dict[str, Any] = {}

        self._searchable_servers: Dict[str, Dict[str, Any]] = {}
        self._bm25_index: BM25Index | None = None
        self._injected_servers: set[str] = set()

        self.enable_permissions = enable_permissions
        if enable_permissions:
            from agent.core.permission_manager import PermissionManager

            self.permission_manager = PermissionManager()
        else:
            self.permission_manager = None

    def load_all(self) -> List[Dict[str, Any]]:
        """Load MCP tools, the shared skill loader, and builtin tools."""
        self.tools = []
        self.tool_executors = {}
        self.tool_instances = {}
        self._searchable_servers = {}
        self._bm25_index = None
        self._injected_servers = set()

        print("Loading tools...")
        self._load_mcp_tools()
        self._load_skills()
        self._load_builtin_tools()
        self._snapshot_catalog()
        print(f"\nOK loaded {len(self.tools)} tools")
        return self.tools

    def _snapshot_catalog(self) -> None:
        self._catalog_tools = copy.deepcopy(self.tools)
        self._catalog_executors = dict(self.tool_executors)
        self._catalog_instances = dict(self.tool_instances)

    def _restore_catalog(self) -> None:
        self.tools = copy.deepcopy(self._catalog_tools)
        self.tool_executors = dict(self._catalog_executors)
        self.tool_instances = dict(self._catalog_instances)

    def _tool_group_for(self, tool_name: str) -> str:
        if tool_name.startswith("mcp__"):
            return "mcp"
        return self.TOOL_GROUPS.get(tool_name, "custom")

    def resolve_tools(self, role_config: RoleConfig | None = None) -> List[Dict[str, Any]]:
        """Filter loaded tools for the current runtime role."""
        if not self._catalog_tools:
            self.load_all()

        self._restore_catalog()
        role = role_config or RoleConfig()
        enabled_groups = set(role.enabled_tool_groups)
        allowed_tools = set(role.allowed_tools)
        denied_tools = set(role.denied_tools)

        if not enabled_groups and not allowed_tools and not denied_tools:
            return self.tools

        def is_allowed(name: str) -> bool:
            if name in denied_tools:
                return False
            if not enabled_groups and not allowed_tools:
                return True
            return name in allowed_tools or self._tool_group_for(name) in enabled_groups

        selected_defs = []
        selected_names = set()
        for tool in self.tools:
            name = tool.get("function", {}).get("name", "")
            if is_allowed(name):
                selected_defs.append(tool)
                selected_names.add(name)

        selected_executors = {
            name: executor
            for name, executor in self.tool_executors.items()
            if name in selected_names or (name == "_mcp_manager" and any(t.startswith("mcp__") or t == "tool_search" for t in selected_names))
        }
        selected_instances = {
            name: instance
            for name, instance in self.tool_instances.items()
            if name in selected_names
        }

        self.tools = selected_defs
        self.tool_executors = selected_executors
        self.tool_instances = selected_instances
        return self.tools

    def configure_runtime(self, workspace_root: Path) -> None:
        """Bind workspace-aware tool instances to the active runtime."""
        self.workspace_root = Path(workspace_root).resolve()
        self.skill_loader.set_workspace_skills_dir(self.workspace_root / "skills")
        for tool in self.tool_instances.values():
            if hasattr(tool, "temp_dir"):
                tool.temp_dir = self.workspace_root

    def _load_mcp_tools(self) -> None:
        """Load MCP tools and defer searchable servers behind tool_search."""
        try:
            from agent.tools.mcp_manager import MCPManager

            print("\n Loading MCP tools...")
            manager = MCPManager(servers_dir=str(self.project_root / "mcp-servers"))
            servers = manager.get_tools_by_server()
            if not servers:
                print("   Warning: no MCP tools found")
                return

            registry = self._load_registry()
            core_count = 0
            searchable_count = 0

            for server_name, server_info in servers.items():
                entry = registry.get(server_name, {})
                category = entry.get("category", DEFAULT_MCP_CATEGORY)
                alias = entry.get("alias", "")
                tools = server_info.get("tools", [])

                if category == "core":
                    self.tools.extend(tools)
                    core_count += len(tools)
                    print(f"   OK [core] {server_name}: {len(tools)} tools")
                else:
                    self._searchable_servers[server_name] = {
                        "tools": tools,
                        "alias": alias,
                        "description": server_info.get("description", ""),
                    }
                    searchable_count += len(tools)
                    print(f"   OK [searchable] {server_name}: {len(tools)} tools (deferred)")

            if self._searchable_servers:
                self._build_search_index()
                self.tools.append(self._create_tool_search_definition())
                print(f"   OK tool_search registered for {len(self._searchable_servers)} servers")

            self.tool_executors["_mcp_manager"] = manager
            total = core_count + searchable_count
            print(f"   OK MCP total: {total} tools ({core_count} core + {searchable_count} searchable)")
        except Exception as exc:
            print(f"   Error: failed to load MCP tools: {exc}")
            import traceback

            traceback.print_exc()

    def _load_registry(self) -> Dict[str, Dict[str, Any]]:
        """Read mcp-servers/registry.json if it exists."""
        registry_path = self.project_root / "mcp-servers" / "registry.json"
        if not registry_path.exists():
            return {}

        try:
            data = json.loads(registry_path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"   Warning: failed to read registry.json: {exc}")
            return {}

        return {key: value for key, value in data.items() if isinstance(value, dict) and not key.startswith("_")}

    def _build_search_index(self) -> None:
        """Build a BM25 index over deferred MCP servers."""
        self._bm25_index = BM25Index()
        for server_name, info in self._searchable_servers.items():
            text_parts = [server_name]
            if info.get("alias"):
                text_parts.append(info["alias"])
            if info.get("description"):
                text_parts.append(info["description"])

            for tool_def in info.get("tools", []):
                function = tool_def.get("function", {})
                text_parts.append(function.get("name", "").replace("__", " ").replace("_", " "))
                text_parts.append(function.get("description", ""))
                parameters = function.get("parameters", {})
                for param_name in parameters.get("properties", {}).keys():
                    text_parts.append(param_name)

            self._bm25_index.add_document(server_name, " ".join(text_parts))

    def _create_tool_search_definition(self) -> Dict[str, Any]:
        """Create the shared tool_search definition."""
        server_lines = []
        for name, info in self._searchable_servers.items():
            line = f"- {name}"
            if info.get("alias"):
                line += f" ({info['alias']})"
            if info.get("description"):
                line += f": {info['description'][:80]}"
            server_lines.append(line)

        description = (
            "Search deferred MCP servers and load the most relevant tools into the current session.\n"
            f"Available servers:\n{chr(10).join(server_lines)}"
        )

        return {
            "type": "function",
            "function": {
                "name": "tool_search",
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "What capability or domain you want to search for.",
                        }
                    },
                    "required": ["query"],
                },
            },
        }

    def _execute_tool_search(self, query: str) -> str:
        """Search deferred servers and inject the best matches into self.tools."""
        if not self._bm25_index:
            return "No searchable MCP servers are available."

        results = self._bm25_index.search(query, top_k=2)
        if not results:
            available = ", ".join(
                f"{name}({info['alias']})" if info.get("alias") else name
                for name, info in self._searchable_servers.items()
            )
            return f"No matching servers found for '{query}'. Available: {available}"

        loaded_info = []
        for server_name, _score in results:
            if server_name in self._injected_servers:
                loaded_info.append(f"{server_name}: already loaded")
                continue

            server_info = self._searchable_servers.get(server_name)
            if not server_info:
                continue

            tools = server_info["tools"]
            self.tools.extend(tools)
            self._injected_servers.add(server_name)
            tool_names = [tool["function"]["name"] for tool in tools]
            loaded_info.append(f"{server_name}: loaded {len(tools)} tools - {', '.join(tool_names)}")

        return "Loaded tools:\n" + "\n".join(loaded_info)

    def _load_skills(self) -> None:
        """Register the shared load_skill tool and refresh skill summaries."""
        print("\n Loading skills...")
        self.skill_loader.reload()
        summaries = self.skill_loader.get_summaries()

        if not summaries:
            if self.skills_dir.exists():
                print(f"   Warning: skills directory is empty or has no valid metadata: {self.skills_dir}")
            else:
                print(f"   Warning: skills directory not found: {self.skills_dir}")
            return

        self.tools.append(self._create_load_skill_definition())
        self.tool_executors["load_skill"] = self._execute_load_skill

        for summary in summaries:
            print(f"   OK {summary['name']}")
        print(f"   OK skills total: {len(summaries)} (body loaded via load_skill)")

    def _create_load_skill_definition(self) -> Dict[str, Any]:
        """Create the shared load_skill tool definition."""
        return {
            "type": "function",
            "function": {
                "name": "load_skill",
                "description": (
                    "Load the full body of a skill by name. "
                    "Use this after reading the skill summaries in the system prompt."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "The skill name from the available skill list.",
                        }
                    },
                    "required": ["name"],
                },
            },
        }

    def _execute_load_skill(self, name: str) -> str:
        """Load a skill body on demand."""
        return self.skill_loader.get_content(name)

    def _load_builtin_tools(self) -> None:
        """Load builtin local tools."""
        print("\n Loading builtin tools...")

        for module_path, class_name, init_kwargs in self.BUILTIN_TOOLS:
            try:
                module = importlib.import_module(module_path)
                tool_class = getattr(module, class_name)
                kwargs = dict(init_kwargs)
                if class_name == "BashTool":
                    kwargs["project_root"] = self.project_root
                tool_instance = tool_class(**kwargs)
                self.tools.append(tool_instance.get_tool_definition())
                self.tool_executors[tool_instance.name] = tool_instance.execute
                self.tool_instances[tool_instance.name] = tool_instance
                print(f"   OK {tool_instance.name}")
            except Exception as exc:
                print(f"   Error: failed to load {class_name}: {exc}")

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool after optional permission checks."""
        sandbox_result = self.sandbox_guard.check_tool_call(
            tool_name,
            arguments,
            auto_mode=self._auto_mode_enabled(),
        )
        if sandbox_result.decision == "deny":
            error = {
                "error": "Sandbox denied",
                "tool": tool_name,
                "reason": sandbox_result.reason,
            }
            if sandbox_result.guidance:
                error["guidance"] = sandbox_result.guidance
            return error

        if self.enable_permissions and self.permission_manager:
            if sandbox_result.decision == "ask":
                result = self.permission_manager.ask_user(tool_name, arguments, sandbox_result.reason)
                if isinstance(result, dict) and "retry_with_context" in result:
                    return {
                        "retry_with_context": result["retry_with_context"],
                        "tool": tool_name,
                        "args": arguments,
                    }
                if not result:
                    error = {"error": "Permission denied by user", "tool": tool_name, "reason": sandbox_result.reason}
                    if sandbox_result.guidance:
                        error["guidance"] = sandbox_result.guidance
                    return error

        if tool_name == "tool_search":
            return self._execute_tool_search(arguments.get("query", ""))

        if tool_name.startswith("mcp__"):
            manager = self.tool_executors.get("_mcp_manager")
            if manager:
                return manager.call_tool(tool_name, arguments)
            return {"error": "MCP Manager not available"}

        if tool_name == "load_skill":
            executor = self.tool_executors.get(tool_name)
            if executor:
                return executor(arguments.get("name", ""))
            return {"error": "Skill loader not available"}

        executor = self.tool_executors.get(tool_name)
        if executor:
            return executor(**arguments)

        return {"error": f"Unknown tool: {tool_name}"}

    def _auto_mode_enabled(self) -> bool:
        return bool(
            self.enable_permissions
            and self.permission_manager
            and getattr(self.permission_manager, "mode", "") == "auto"
        )

    def get_tools(self) -> List[Dict[str, Any]]:
        """Return the currently registered tools."""
        return self.tools


if __name__ == "__main__":
    print("=" * 70)
    print("Tool Loader Test")
    print("=" * 70)

    loader = ToolLoader()
    tools = loader.load_all()

    print("\n" + "=" * 70)
    print("Tool List")
    print("=" * 70)

    mcp_tools = [tool for tool in tools if tool["function"]["name"].startswith("mcp__")]
    skill_tools = [tool for tool in tools if tool["function"]["name"] == "load_skill"]
    builtin_tools = [
        tool
        for tool in tools
        if not tool["function"]["name"].startswith("mcp__") and tool["function"]["name"] != "load_skill"
    ]

    if mcp_tools:
        print(f"\nMCP Tools ({len(mcp_tools)}):")
        for tool in mcp_tools[:5]:
            print(f"   - {tool['function']['name']}")
        if len(mcp_tools) > 5:
            print(f"   ... and {len(mcp_tools) - 5} more")

    if skill_tools:
        print(f"\nSkill Tools ({len(skill_tools)}):")
        for tool in skill_tools:
            print(f"   - {tool['function']['name']}: {tool['function']['description'][:50]}...")

    if builtin_tools:
        print(f"\nBuiltin Tools ({len(builtin_tools)}):")
        for tool in builtin_tools:
            print(f"   - {tool['function']['name']}")

    print(f"\nTotal: {len(tools)} tools loaded")
