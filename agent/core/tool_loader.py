"""
工具加载器 - 自动加载所有工具（MCP + Skills + 内置）
"""

import json
import importlib
from pathlib import Path
from typing import List, Dict, Any

from agent.core.config import BASH_TOOL_TIMEOUT, DEFAULT_MCP_CATEGORY
from agent.core.bm25 import BM25Index


class ToolLoader:
    """统一的工具加载器"""

    def __init__(self, project_root: Path = None, enable_permissions: bool = True):
        """
        初始化工具加载器

        Args:
            project_root: 项目根目录
            enable_permissions: 是否启用权限系统
        """
        if project_root is None:
            # 自动检测项目根目录
            current = Path(__file__).parent
            self.project_root = current.parent.parent
        else:
            self.project_root = Path(project_root)

        self.skills_dir = self.project_root / "skills"
        self.tools = []
        self.tool_executors = {}  # 工具名 -> 执行函数
        self.tool_instances = {}  # 工具名 -> 实例

        # Tool Search 状态
        self._searchable_servers = {}   # {server_name: {tools, alias, description}}
        self._bm25_index = None         # BM25Index
        self._injected_servers = set()  # 已注入的 server，防重复

        # 初始化权限管理器
        self.enable_permissions = enable_permissions
        if enable_permissions:
            from agent.core.permission_manager import PermissionManager
            self.permission_manager = PermissionManager()
        else:
            self.permission_manager = None

    def load_all(self) -> List[Dict[str, Any]]:
        """
        加载所有工具

        Returns:
            工具列表（OpenAI format）
        """
        self.tools = []
        self.tool_executors = {}

        print("Loading tools...")

        # 1. 加载 MCP 工具
        self._load_mcp_tools()

        # 2. 加载 Skills
        self._load_skills()

        # 3. 加载内置工具（Bash）
        self._load_builtin_tools()

        print(f"\nOK 加载完成，共 {len(self.tools)} 个工具\n")

        return self.tools

    def _load_mcp_tools(self):
        """加载 MCP 工具（按 registry.json 分类：core 常驻 / searchable 按需搜索）"""
        try:
            from agent.tools.mcp_manager import MCPManager

            print("\n 加载 MCP 工具...")
            mcp_servers_dir = str(self.project_root / "mcp-servers")
            manager = MCPManager(servers_dir=mcp_servers_dir)

            # 按 server 分组获取工具
            servers = manager.get_tools_by_server()
            if not servers:
                print(f"   Warning:  未找到 MCP 工具")
                return

            # 读取分类注册表
            registry = self._load_registry()

            core_count = 0
            searchable_count = 0

            for server_name, server_info in servers.items():
                entry = registry.get(server_name, {})
                category = entry.get('category', DEFAULT_MCP_CATEGORY)
                alias = entry.get('alias', '')
                tools = server_info.get('tools', [])

                if category == 'core':
                    self.tools.extend(tools)
                    core_count += len(tools)
                    print(f"   OK [core] {server_name}: {len(tools)} 个工具")
                else:
                    self._searchable_servers[server_name] = {
                        'tools': tools,
                        'alias': alias,
                        'description': server_info.get('description', ''),
                    }
                    searchable_count += len(tools)
                    print(f"   OK [searchable] {server_name}: {len(tools)} 个工具 (deferred)")

            # 如果有 searchable servers，构建搜索索引并注入 tool_search
            if self._searchable_servers:
                self._build_search_index()
                search_tool_def = self._create_tool_search_definition()
                self.tools.append(search_tool_def)
                print(f"   tool_search 已创建（{len(self._searchable_servers)} 个 searchable server，{searchable_count} 个隐藏工具）")

            # 保存 manager 用于调用
            self.tool_executors['_mcp_manager'] = manager

            total = core_count + searchable_count
            print(f"   OK MCP 总计: {total}（{core_count} core + {searchable_count} searchable）")

        except Exception as e:
            print(f"   Error: MCP 加载失败: {e}")
            import traceback
            traceback.print_exc()

    def _load_registry(self) -> Dict:
        """读取 mcp-servers/registry.json 分类配置"""
        registry_path = self.project_root / "mcp-servers" / "registry.json"
        if registry_path.exists():
            try:
                data = json.loads(registry_path.read_text(encoding='utf-8'))
                # 过滤掉 _comment 等非 server 字段
                return {k: v for k, v in data.items() if isinstance(v, dict) and not k.startswith('_')}
            except Exception as e:
                print(f"   Warning: registry.json 读取失败: {e}")
        return {}

    def _build_search_index(self):
        """为 searchable servers 构建 BM25 搜索索引"""
        self._bm25_index = BM25Index()

        for server_name, info in self._searchable_servers.items():
            text_parts = [server_name]

            if info.get('alias'):
                text_parts.append(info['alias'])
            if info.get('description'):
                text_parts.append(info['description'])

            for tool_def in info.get('tools', []):
                func = tool_def.get('function', {})
                text_parts.append(func.get('name', '').replace('__', ' ').replace('_', ' '))
                text_parts.append(func.get('description', ''))
                params = func.get('parameters', {})
                for param_name in params.get('properties', {}).keys():
                    text_parts.append(param_name)

            self._bm25_index.add_document(server_name, ' '.join(text_parts))

    def _create_tool_search_definition(self) -> Dict[str, Any]:
        """创建 tool_search 工具定义（description 自动列出所有 searchable server）"""
        server_lines = []
        for name, info in self._searchable_servers.items():
            alias = info.get('alias', '')
            desc = info.get('description', '')[:80]
            line = f"- {name}"
            if alias:
                line += f" ({alias})"
            if desc:
                line += f": {desc}"
            server_lines.append(line)

        servers_list = '\n'.join(server_lines)

        description = (
            f"搜索可用的 MCP 工具（共 {len(self._searchable_servers)} 个 server）。"
            f"当你需要使用以下服务时，先调用此工具搜索：\n"
            f"{servers_list}\n"
            f"搜索后工具会被加载，你可以直接调用。"
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
                            "description": "搜索关键词（server 名称、别名或功能描述）"
                        }
                    },
                    "required": ["query"]
                }
            }
        }

    def _execute_tool_search(self, query: str) -> str:
        """执行工具搜索：匹配 server 并将其工具注入到 self.tools"""
        if not self._bm25_index:
            return "没有可搜索的工具。"

        results = self._bm25_index.search(query, top_k=2)

        if not results:
            available = ', '.join(
                f"{name}({info.get('alias', '')})" if info.get('alias') else name
                for name, info in self._searchable_servers.items()
            )
            return f"未找到匹配 '{query}' 的工具。可用 servers: {available}"

        loaded_info = []
        for server_name, score in results:
            if server_name in self._injected_servers:
                loaded_info.append(f"{server_name}: 已加载")
                continue

            server_info = self._searchable_servers.get(server_name)
            if not server_info:
                continue

            tools = server_info['tools']
            self.tools.extend(tools)
            self._injected_servers.add(server_name)

            tool_names = [t['function']['name'] for t in tools]
            loaded_info.append(f"{server_name}: 加载了 {len(tools)} 个工具 - {', '.join(tool_names)}")

        return "工具已加载：\n" + '\n'.join(loaded_info) + "\n\n请直接调用上述工具完成任务。"

    def _load_skills(self):
        """加载 Skills（.md 文件）"""
        print("\n 加载 Skills...")

        if not self.skills_dir.exists():
            print(f"   Warning:  Skills 目录不存在: {self.skills_dir}")
            return

        skill_count = 0

        # 递归查找所有 .md 文件
        for md_file in self.skills_dir.rglob("*.md"):
            try:
                skill = self._parse_skill(md_file)
                if skill:
                    self.tools.append(skill['tool_def'])
                    self.tool_executors[skill['tool_name']] = skill['executor']
                    skill_count += 1
                    print(f"   OK {skill['name']}")

            except Exception as e:
                print(f"   Error: 解析失败 {md_file.name}: {e}")

        if skill_count > 0:
            print(f"    Skills: {skill_count} 个")
        else:
            print(f"   Warning:  未找到 Skills")

    def _parse_skill(self, md_file: Path) -> Dict[str, Any] | None:
        """
        解析 Skill .md 文件

        格式:
        ---
        name: skill-name
        description: Skill description
        ---
        Full content...

        Returns:
            解析后的 skill 信息
        """
        content = md_file.read_text(encoding='utf-8')

        # 检查是否有 YAML frontmatter
        if not content.startswith('---'):
            return None

        # 提取 frontmatter
        parts = content.split('---', 2)
        if len(parts) < 3:
            return None

        frontmatter = parts[1].strip()
        full_content = parts[2].strip()

        # 简单解析 YAML（只解析 name 和 description）
        metadata = {}
        for line in frontmatter.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                metadata[key.strip()] = value.strip()

        name = metadata.get('name')
        description = metadata.get('description', '')

        if not name:
            return None

        # 工具名称格式：skill__<name>
        tool_name = f"skill__{name.replace('-', '_')}"

        # 创建工具定义
        tool_def = {
            "type": "function",
            "function": {
                "name": tool_name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "查询或任务描述"
                        }
                    },
                    "required": ["query"]
                }
            }
        }

        # 创建执行器（返回全文）
        def skill_executor(query: str) -> str:
            """Skill 执行器 - 返回完整内容"""
            return f"=== Skill: {name} ===\n\n{full_content}"

        return {
            "name": name,
            "tool_name": tool_name,
            "tool_def": tool_def,
            "executor": skill_executor,
            "file": md_file
        }

    # 内置工具注册表：(模块路径, 类名, 构造参数)
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

    def _load_builtin_tools(self):
        """加载内置工具（通过注册表自动发现）"""
        print("\n  加载内置工具...")

        for module_path, class_name, init_kwargs in self.BUILTIN_TOOLS:
            try:
                module = importlib.import_module(module_path)
                tool_class = getattr(module, class_name)
                tool_instance = tool_class(**init_kwargs)

                self.tools.append(tool_instance.get_tool_definition())
                self.tool_executors[tool_instance.name] = tool_instance.execute
                self.tool_instances[tool_instance.name] = tool_instance
                print(f"   OK {tool_instance.name.capitalize()}")
            except Exception as e:
                print(f"   Error: {class_name} 加载失败: {e}")

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        执行工具

        Args:
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            执行结果
        """
        # ========================================
        # 权限检查
        # ========================================
        if self.enable_permissions and self.permission_manager:
            permission = self.permission_manager.check_permission(tool_name, arguments)

            # 拒绝
            if permission == "deny":
                return {
                    "error": "Permission denied",
                    "tool": tool_name,
                    "reason": "This operation is blocked by permission rules"
                }

            # 询问用户
            if permission == "ask":
                result = self.permission_manager.ask_user(tool_name, arguments)

                # 检查是否是重试请求（带额外指令）
                if isinstance(result, dict) and "retry_with_context" in result:
                    return {
                        "retry_with_context": result["retry_with_context"],
                        "tool": tool_name,
                        "args": arguments
                    }

                # 传统的允许/拒绝
                if not result:
                    return {
                        "error": "Permission denied by user",
                        "tool": tool_name
                    }

        # ========================================
        # 执行工具
        # ========================================

        # Tool Search（动态工具注入）
        if tool_name == "tool_search":
            return self._execute_tool_search(arguments.get('query', ''))

        # MCP 工具（特殊路由：通过 MCPManager 调用）
        if tool_name.startswith("mcp__"):
            manager = self.tool_executors.get('_mcp_manager')
            if manager:
                return manager.call_tool(tool_name, arguments)
            return {"error": "MCP Manager not available"}

        # Skill 工具（特殊路由：只传 query 参数）
        if tool_name.startswith("skill__"):
            executor = self.tool_executors.get(tool_name)
            if executor:
                return executor(arguments.get('query', ''))
            return {"error": f"Skill not found: {tool_name}"}

        # 内置工具（统一 **kwargs 分发）
        executor = self.tool_executors.get(tool_name)
        if executor:
            return executor(**arguments)

        return {"error": f"Unknown tool: {tool_name}"}

    def get_tools(self) -> List[Dict[str, Any]]:
        """获取所有工具列表"""
        return self.tools


# ============================================
# 使用示例
# ============================================

if __name__ == "__main__":
    # Add project root to path
    import sys
    project_root = Path(__file__).parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    print("=" * 70)
    print("Tool Loader Test")
    print("=" * 70)

    loader = ToolLoader()
    tools = loader.load_all()

    print("\n" + "=" * 70)
    print("Tool List")
    print("=" * 70)

    # Group by type
    mcp_tools = [t for t in tools if t['function']['name'].startswith('mcp__')]
    skill_tools = [t for t in tools if t['function']['name'].startswith('skill__')]
    builtin_tools = [t for t in tools if not t['function']['name'].startswith(('mcp__', 'skill__'))]

    if mcp_tools:
        print(f"\nMCP Tools ({len(mcp_tools)}):")
        for tool in mcp_tools[:5]:
            print(f"   - {tool['function']['name']}")
        if len(mcp_tools) > 5:
            print(f"   ... and {len(mcp_tools) - 5} more")

    if skill_tools:
        print(f"\nSkills ({len(skill_tools)}):")
        for tool in skill_tools:
            name = tool['function']['name']
            desc = tool['function']['description'][:50]
            print(f"   - {name}: {desc}...")

    if builtin_tools:
        print(f"\nBuiltin Tools ({len(builtin_tools)}):")
        for tool in builtin_tools:
            print(f"   - {tool['function']['name']}")

    print(f"\nTotal: {len(tools)} tools loaded")
