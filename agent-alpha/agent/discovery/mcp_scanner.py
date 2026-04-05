"""
MCP Scanner - 自动扫描和识别 MCP servers
"""

import json
from pathlib import Path
from typing import Dict, Any


class MCPScanner:
    """自动扫描 mcp-servers 目录，识别各种类型的 MCP server"""

    def __init__(self, servers_dir: str = "mcp-servers"):
        self.servers_dir = Path(servers_dir)
        self.servers_dir.mkdir(exist_ok=True)

    def scan(self) -> Dict[str, Dict[str, Any]]:
        """
        扫描目录，返回所有发现的 MCP server 配置

        Returns:
            字典格式：{server_name: server_config}
        """
        discovered_servers = {}

        if not self.servers_dir.exists():
            print(f"⚠️  目录不存在: {self.servers_dir}")
            return discovered_servers

        for server_dir in self.servers_dir.iterdir():
            if not server_dir.is_dir() or server_dir.name.startswith('.'):
                continue

            server_name = server_dir.name
            config = self._detect_server_type(server_dir)

            if config:
                discovered_servers[server_name] = config
                print(f"✅ 发现 MCP server: {server_name} ({config.get('type', 'unknown')})")
            else:
                print(f"⚠️  无法识别: {server_name}")

        return discovered_servers

    def _detect_server_type(self, server_dir: Path) -> Dict[str, Any] | None:
        """
        检测 server 类型并返回配置

        优先级:
        1. mcp.config.json (自定义配置)
        2. package.json (Node.js)
        3. pyproject.toml (Python)
        4. 可执行文件
        """

        # 1. 检查自定义配置文件
        config_file = server_dir / "mcp.config.json"
        if config_file.exists():
            return self._load_custom_config(config_file)

        # 2. 检查 Node.js 项目
        package_json = server_dir / "package.json"
        if package_json.exists():
            return self._detect_nodejs_server(package_json, server_dir)

        # 3. 检查 Python 项目
        pyproject_toml = server_dir / "pyproject.toml"
        if pyproject_toml.exists():
            return self._detect_python_server(pyproject_toml, server_dir)

        # 4. 检查可执行文件
        return self._detect_executable_server(server_dir)

    def _load_custom_config(self, config_file: Path) -> Dict[str, Any] | None:
        """加载自定义 mcp.config.json（支持扁平格式和 Claude Desktop 嵌套格式）"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # 检测是否是 Claude Desktop 嵌套格式
            if 'mcpServers' in config:
                # 提取第一个 server 的配置
                servers = config['mcpServers']
                if not servers:
                    print(f"  ❌ mcpServers 为空: {config_file.parent.name}")
                    return None

                # 获取第一个 server（如果有多个，使用第一个）
                server_name = list(servers.keys())[0]
                server_config = servers[server_name]

                print(f"  📦 检测到 Claude Desktop 格式，提取 server: {server_name}")

                # 转换为扁平格式继续处理
                config = {
                    'enabled': True,  # 默认启用
                    'type': 'stdio',  # 默认 stdio（如果 server_config 中有 type 会覆盖）
                    **server_config   # 合并 server 配置
                }

            # 检查是否启用
            if not config.get('enabled', True):
                print(f"  ⏭️  跳过（已禁用）: {config_file.parent.name}")
                return None

            server_type = config.get('type', 'stdio')

            # 根据类型构建配置
            if server_type == 'http':
                # HTTP 类型需要 url 和可选的 headers
                if 'url' not in config:
                    print(f"  ❌ HTTP 配置缺少 url: {config_file.parent.name}")
                    return None

                return {
                    'type': 'http',
                    'url': config['url'],
                    'headers': config.get('headers', {}),
                    'description': config.get('description', ''),
                    'auto_start': config.get('auto_start', {}),  # 传递 auto_start 配置
                    'source': 'custom'
                }
            else:
                # stdio 类型需要 command
                if 'command' not in config:
                    print(f"  ❌ stdio 配置缺少 command: {config_file.parent.name}")
                    return None

                return {
                    'type': 'stdio',
                    'command': config['command'],
                    'args': config.get('args', []),
                    'env': config.get('env', {}),
                    'cwd': str(config_file.parent.resolve()),
                    'description': config.get('description', ''),
                    'source': 'custom'
                }
        except Exception as e:
            print(f"  ❌ 配置文件错误: {e}")
            return None

    def _detect_nodejs_server(self, package_json: Path, server_dir: Path) -> Dict[str, Any] | None:
        """检测 Node.js MCP server"""
        try:
            with open(package_json, 'r', encoding='utf-8') as f:
                pkg = json.load(f)

            # 检查是否是 MCP server
            keywords = pkg.get('keywords', [])
            if 'mcp' not in keywords and 'mcp-server' not in keywords:
                # 尝试检查 dependencies
                deps = {**pkg.get('dependencies', {}), **pkg.get('devDependencies', {})}
                if not any('mcp' in dep.lower() for dep in deps.keys()):
                    return None

            package_name = pkg.get('name', server_dir.name)

            return {
                'type': 'stdio',
                'command': 'npx',
                'args': ['-y', package_name],
                'env': {},
                'description': pkg.get('description', ''),
                'source': 'nodejs',
                'version': pkg.get('version', 'unknown')
            }
        except Exception as e:
            print(f"  ❌ Node.js 检测失败: {e}")
            return None

    def _detect_python_server(self, pyproject_toml: Path, server_dir: Path) -> Dict[str, Any] | None:
        """检测 Python MCP server"""
        try:
            # 简单解析（避免依赖 toml 库）
            content = pyproject_toml.read_text(encoding='utf-8')

            # 检查是否包含 mcp 相关依赖
            if 'mcp' not in content.lower():
                return None

            # 从目录名获取包名
            package_name = server_dir.name

            return {
                'type': 'stdio',
                'command': 'uvx',
                'args': [package_name],
                'env': {},
                'description': f'Python MCP server: {package_name}',
                'source': 'python'
            }
        except Exception as e:
            print(f"  ❌ Python 检测失败: {e}")
            return None

    def _detect_executable_server(self, server_dir: Path) -> Dict[str, Any] | None:
        """检测可执行文件"""
        # 查找常见的可执行文件
        for pattern in ['mcp-server*', 'server*', '*.exe']:
            for exe_file in server_dir.glob(pattern):
                if exe_file.is_file() and (exe_file.suffix in ['.exe', ''] or exe_file.stat().st_mode & 0o111):
                    return {
                        'type': 'stdio',
                        'command': str(exe_file),
                        'args': [],
                        'env': {},
                        'description': f'Executable MCP server: {exe_file.name}',
                        'source': 'executable'
                    }

        return None

    def save_config(self, servers: Dict[str, Dict[str, Any]], output_file: str = ".auto-config.json"):
        """
        保存自动生成的配置

        将配置保存到每个 MCP server 的目录下
        """
        saved_configs = []

        for server_name, server_config in servers.items():
            # 构建配置对象（单个 server）
            config = {
                "_comment": "此文件由 MCP Scanner 自动生成，请勿手动编辑",
                "name": server_name,
                **server_config
            }

            # 保存到 server 目录
            server_dir = self.servers_dir / server_name
            server_dir.mkdir(parents=True, exist_ok=True)

            config_path = server_dir / "auto-config.json"
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            saved_configs.append(str(config_path))

        if saved_configs:
            print(f"\n💾 配置已保存:")
            for path in saved_configs:
                print(f"   - {path}")

        return saved_configs


if __name__ == "__main__":
    # 测试扫描
    scanner = MCPScanner()
    servers = scanner.scan()

    if servers:
        scanner.save_config(servers)
        print(f"\n✅ 发现 {len(servers)} 个 MCP servers")
    else:
        print("\n⚠️  未发现任何 MCP servers")
        print("提示：将 MCP server 项目放到 mcp-servers/ 目录下")
