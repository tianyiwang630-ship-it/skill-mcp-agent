"""
MCP Manager - 使用 FastMCP 管理 MCP servers（持久连接版）

核心设计：
- 后台事件循环保持所有 MCP 连接持久化
- 连接一次，所有操作复用同一会话
- 支持 STDIO 和 HTTP 两种传输方式
- STDIO wrapper 自动过滤非 JSON-RPC 输出
"""

import asyncio
import json
import threading
from pathlib import Path
from typing import Dict, List, Any

try:
    from fastmcp import Client
    FASTMCP_AVAILABLE = True
except ImportError:
    FASTMCP_AVAILABLE = False
    print("⚠️  fastmcp 未安装，请运行: pip install fastmcp")

from agent.discovery.mcp_scanner import MCPScanner


class MCPManager:
    """MCP 工具管理器 - 持久连接，自动发现"""

    def __init__(self, servers_dir: str = "mcp-servers", auto_discover: bool = True):
        if not FASTMCP_AVAILABLE:
            raise ImportError("fastmcp 库未安装")

        self.servers_dir = servers_dir
        self.scanner = MCPScanner(servers_dir)
        self.servers = {}  # server 状态信息

        # 后台事件循环（保持连接持久化）
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()

        # 连接管理
        self._clients = {}      # server_name -> Client 实例
        self._connected = {}    # server_name -> 已连接的 Client（async with 后）

        if auto_discover:
            self.discover_and_connect()

    def _run_coro(self, coro, timeout=60):
        """在后台事件循环中运行协程"""
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)

    # ==========================================
    # 发现与连接
    # ==========================================

    def discover_and_connect(self):
        """自动发现并连接所有 MCP servers"""
        print("\n🔍 扫描 MCP servers...")

        discovered = self.scanner.scan()
        if not discovered:
            print("⚠️  未发现任何 MCP servers")
            print(f"💡 提示：将 MCP server 项目克隆到 {self.servers_dir}/ 目录")
            return

        self.scanner.save_config(discovered)

        # 创建 Client 实例
        print("\n🔌 连接 MCP servers...")
        for server_name, config in discovered.items():
            self._create_client(server_name, config)

        # 在后台事件循环中连接所有 servers（持久化）
        self._run_coro(self._connect_all(), timeout=120)

        connected = len(self._connected)
        total = len(self._clients)
        print(f"\n✅ 成功连接 {connected}/{total} 个 servers")

    def _get_wrapper_path(self) -> str:
        """获取 stdio_wrapper.py 的绝对路径"""
        wrapper = Path(__file__).parent / "stdio_wrapper.py"
        return str(wrapper.resolve())

    def _create_client(self, server_name: str, config: Dict[str, Any]):
        """创建 FastMCP Client 实例

        STDIO 服务器自动通过 stdio_wrapper.py 包装，
        过滤非 JSON-RPC 的 stdout 输出（如调试日志），
        确保任何 MCP server 都能正常工作，无需额外配置。
        """
        try:
            server_type = config.get('type', 'stdio')

            if server_type == 'http':
                url = config['url']
                client = Client(url)
            else:
                # STDIO: 自动通过 wrapper 过滤 stdout
                wrapper_path = self._get_wrapper_path()
                original_command = config['command']
                original_args = config.get('args', [])

                server_config = {
                    'command': 'python',
                    'args': [wrapper_path, original_command] + original_args,
                }
                if config.get('env'):
                    server_config['env'] = config['env']
                if config.get('cwd'):
                    server_config['cwd'] = config['cwd']

                wrapped_config = {
                    'mcpServers': {
                        server_name: server_config
                    }
                }
                client = Client(wrapped_config)

            self._clients[server_name] = client
            self.servers[server_name] = {
                'config': config,
                'status': 'pending',
                'tools': []
            }

        except Exception as e:
            self.servers[server_name] = {
                'config': config,
                'status': 'failed',
                'error': str(e)
            }
            print(f"  ❌ {server_name}: {e}")

    async def _connect_all(self):
        """连接所有 clients（保持连接持久化）"""
        for name, client in self._clients.items():
            try:
                # __aenter__ 启动后台 session_runner 任务
                # 该任务会一直运行直到 __aexit__ 被调用
                connected = await client.__aenter__()
                self._connected[name] = connected
                self.servers[name]['status'] = 'connected'

                server_type = self.servers[name]['config'].get('type', 'stdio')
                print(f"  ✅ {name} ({server_type})")

            except Exception as e:
                self.servers[name]['status'] = 'failed'
                self.servers[name]['error'] = str(e)
                print(f"  ❌ {name}: {e}")

    # ==========================================
    # 工具操作（复用持久连接）
    # ==========================================

    def get_all_tools(self) -> List[Dict[str, Any]]:
        """获取所有 MCP 工具（OpenAI function calling 格式）"""
        try:
            tools = self._run_coro(self._async_get_all_tools())
            print(f"\n📦 可用工具数: {len(tools)}")
            return tools
        except Exception as e:
            print(f"❌ 获取工具失败: {e}")
            import traceback
            traceback.print_exc()
            return []

    async def _async_get_all_tools(self) -> List[Dict[str, Any]]:
        """异步获取所有工具"""
        all_tools = []
        for server_name, client in self._connected.items():
            try:
                tools = await client.list_tools()
                for tool in tools:
                    tool_name = f"mcp__{server_name}__{tool.name}"
                    tool_def = {
                        'type': 'function',
                        'function': {
                            'name': tool_name,
                            'description': tool.description or '',
                            'parameters': tool.inputSchema or {
                                'type': 'object',
                                'properties': {}
                            }
                        }
                    }
                    all_tools.append(tool_def)
            except Exception as e:
                print(f"  ⚠️  {server_name} 获取工具失败: {e}")
        return all_tools

    def get_tools_by_server(self) -> Dict[str, Dict[str, Any]]:
        """
        获取按 server 分组的工具列表（附 server 元信息）

        Returns:
            {server_name: {description, tools: [tool_def...]}}
        """
        try:
            return self._run_coro(self._async_get_tools_by_server())
        except Exception as e:
            print(f"❌ 获取分组工具失败: {e}")
            import traceback
            traceback.print_exc()
            return {}

    async def _async_get_tools_by_server(self) -> Dict[str, Dict[str, Any]]:
        """异步获取按 server 分组的工具"""
        result = {}
        for server_name, client in self._connected.items():
            server_info = self.servers.get(server_name, {})
            config = server_info.get('config', {})

            tools_list = []
            try:
                tools = await client.list_tools()
                for tool in tools:
                    tool_name = f"mcp__{server_name}__{tool.name}"
                    tool_def = {
                        'type': 'function',
                        'function': {
                            'name': tool_name,
                            'description': tool.description or '',
                            'parameters': tool.inputSchema or {
                                'type': 'object',
                                'properties': {}
                            }
                        }
                    }
                    tools_list.append(tool_def)
            except Exception as e:
                print(f"  ⚠️  {server_name} 获取工具失败: {e}")

            result[server_name] = {
                'description': config.get('description', ''),
                'tools': tools_list
            }

        total = sum(len(s['tools']) for s in result.values())
        print(f"\n📦 可用工具数: {total}（{len(result)} 个 servers）")
        return result

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """调用 MCP 工具（复用持久连接）"""
        try:
            # 解析工具名称: mcp__<server>__<tool_name>
            if not tool_name.startswith('mcp__'):
                return {'error': f'Invalid MCP tool name: {tool_name}'}

            parts = tool_name.split('__')
            if len(parts) < 3:
                return {'error': f'Invalid MCP tool name format: {tool_name}'}

            server_name = parts[1]
            actual_tool_name = '__'.join(parts[2:])

            client = self._connected.get(server_name)
            if not client:
                return {'error': f'Server not connected: {server_name}'}

            # 在后台事件循环中调用
            result = self._run_coro(
                client.call_tool(actual_tool_name, arguments),
                timeout=120
            )

            # 提取文本内容
            if hasattr(result, 'content'):
                content_parts = []
                for item in result.content:
                    if hasattr(item, 'text'):
                        content_parts.append(item.text)
                return '\n'.join(content_parts) if content_parts else str(result)
            else:
                return str(result)

        except Exception as e:
            import traceback
            import re
            # 清理 ANSI 转义码（Playwright 等工具输出包含终端颜色码，部分 LLM API 不接受）
            error_msg = re.sub(r'\x1b\[[0-9;]*m', '', str(e))
            # 只保留错误摘要，不传完整 traceback 给 LLM（减少 token + 避免特殊字符触发 API 校验）
            traceback.print_exc()  # 仍打印到控制台供调试
            return {
                'error': error_msg,
                'tool': tool_name
            }

    # ==========================================
    # 状态与生命周期
    # ==========================================

    def get_server_status(self) -> Dict[str, Any]:
        """获取所有 server 的状态"""
        return {
            'total': len(self.servers),
            'connected': len(self._connected),
            'failed': len([s for s in self.servers.values() if s['status'] == 'failed']),
            'servers': self.servers
        }

    def reload(self):
        """重新扫描和连接（热重载）"""
        print("\n🔄 重新加载 MCP servers...")
        self.close_all()
        self._clients = {}
        self._connected = {}
        self.servers = {}
        self.discover_and_connect()

    def close_all(self):
        """关闭所有持久连接并停止事件循环"""
        async def _close():
            for _, client in list(self._connected.items()):
                try:
                    await asyncio.wait_for(
                        client.__aexit__(None, None, None),
                        timeout=3
                    )
                except Exception:
                    pass
            self._connected.clear()

        try:
            self._run_coro(_close(), timeout=5)
        except Exception:
            pass

        # 停止事件循环，让后台线程退出
        try:
            self._loop.call_soon_threadsafe(self._loop.stop)
        except Exception:
            pass
        print("✅ 所有 MCP 连接已关闭")

    def __del__(self):
        """析构时清理资源"""
        try:
            if self._connected:
                self.close_all()
            else:
                self._loop.call_soon_threadsafe(self._loop.stop)
        except Exception:
            pass


# 使用示例
if __name__ == "__main__":
    manager = MCPManager()

    status = manager.get_server_status()
    print(f"\n📊 状态统计:")
    print(f"  总数: {status['total']}")
    print(f"  已连接: {status['connected']}")
    print(f"  失败: {status['failed']}")

    tools = manager.get_all_tools()
    if tools:
        print(f"\n🔧 可用工具:")
        for tool in tools[:5]:
            print(f"  - {tool['function']['name']}: {tool['function']['description']}")
        if len(tools) > 5:
            print(f"  ... 还有 {len(tools) - 5} 个工具")
