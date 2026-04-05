"""
Grep Tool - 使用正则表达式搜索文件内容（基于 ripgrep）
"""

import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

from agent.tools.base_tool import BaseTool


class GrepTool(BaseTool):
    """内容搜索工具 - 基于 ripgrep"""

    @property
    def name(self) -> str:
        return "grep"

    def __init__(self):
        """初始化 Grep Tool"""
        self.rg_available = self._check_ripgrep()

    def _check_ripgrep(self) -> bool:
        """检查 ripgrep 是否可用"""
        try:
            result = subprocess.run(
                ["rg", "--version"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False

    def get_tool_definition(self) -> Dict[str, Any]:
        """
        返回 OpenAI function calling 格式的工具定义

        Returns:
            工具定义（OpenAI format）
        """
        return {
            "type": "function",
            "function": {
                "name": "grep",
                "description": "使用正则表达式搜索文件内容。基于 ripgrep (rg)，支持复杂的搜索模式和上下文显示。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "正则表达式搜索模式"
                        },
                        "path": {
                            "type": "string",
                            "description": "搜索路径（可选，默认为当前目录）"
                        },
                        "glob": {
                            "type": "string",
                            "description": "文件过滤模式，如 '*.py' 或 '*.{js,ts}'（可选）"
                        },
                        "output_mode": {
                            "type": "string",
                            "enum": ["content", "files_with_matches", "count"],
                            "description": "输出模式：content（显示匹配内容）, files_with_matches（只显示文件路径，默认）, count（显示匹配计数）",
                            "default": "files_with_matches"
                        },
                        "case_insensitive": {
                            "type": "boolean",
                            "description": "忽略大小写（可选，默认 false）",
                            "default": False
                        },
                        "show_line_numbers": {
                            "type": "boolean",
                            "description": "显示行号（可选，默认 true，仅在 content 模式有效）",
                            "default": True
                        },
                        "context_after": {
                            "type": "integer",
                            "description": "显示匹配后 N 行（可选，仅在 content 模式有效）"
                        },
                        "context_before": {
                            "type": "integer",
                            "description": "显示匹配前 N 行（可选，仅在 content 模式有效）"
                        },
                        "context": {
                            "type": "integer",
                            "description": "显示匹配前后 N 行（可选，仅在 content 模式有效）"
                        }
                    },
                    "required": ["pattern"]
                }
            }
        }

    def execute(self, **kwargs) -> str:
        """
        执行内容搜索

        Args (via kwargs):
            pattern: 正则表达式模式
            path: 搜索路径
            glob: 文件过滤模式
            output_mode: 输出模式
            case_insensitive: 是否忽略大小写
            show_line_numbers: 是否显示行号
            context_after: 匹配后显示 N 行
            context_before: 匹配前显示 N 行
            context: 匹配前后显示 N 行

        Returns:
            搜索结果
        """
        pattern = kwargs.get('pattern', '')
        path = kwargs.get('path')
        glob = kwargs.get('glob')
        output_mode = kwargs.get('output_mode', 'files_with_matches')
        case_insensitive = kwargs.get('case_insensitive', False)
        show_line_numbers = kwargs.get('show_line_numbers', True)
        context_after = kwargs.get('context_after')
        context_before = kwargs.get('context_before')
        context = kwargs.get('context')
        # 检查 ripgrep 是否可用
        if not self.rg_available:
            return "Error: ripgrep (rg) is not installed or not available in PATH.\nInstall it from: https://github.com/BurntSushi/ripgrep#installation"

        try:
            # 构建 rg 命令
            cmd = ["rg"]

            # 输出模式
            if output_mode == "files_with_matches":
                cmd.append("-l")  # 只显示文件路径
            elif output_mode == "count":
                cmd.append("-c")  # 显示计数

            # 忽略大小写
            if case_insensitive:
                cmd.append("-i")

            # 显示行号（仅在 content 模式）
            if output_mode == "content" and show_line_numbers:
                cmd.append("-n")

            # 上下文行
            if context is not None and output_mode == "content":
                cmd.extend(["-C", str(context)])
            else:
                if context_after is not None and output_mode == "content":
                    cmd.extend(["-A", str(context_after)])
                if context_before is not None and output_mode == "content":
                    cmd.extend(["-B", str(context_before)])

            # 文件过滤
            if glob:
                cmd.extend(["-g", glob])

            # 搜索模式
            cmd.append(pattern)

            # 搜索路径
            if path:
                # 检查路径是否存在
                path_obj = Path(path)
                if not path_obj.exists():
                    return f"Error: Path does not exist: {path}"
                cmd.append(path)

            # 执行命令
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            # 处理结果
            if result.returncode == 0:
                # 找到匹配
                output = result.stdout.strip()

                # 添加头部信息
                header = f"# Search pattern: '{pattern}'"
                if path:
                    header += f" in '{path}'"
                if glob:
                    header += f" (filter: {glob})"
                header += f"\n# Mode: {output_mode}\n"

                return header + output

            elif result.returncode == 1:
                # 没有找到匹配
                msg = f"No matches found for pattern: '{pattern}'"
                if path:
                    msg += f" in '{path}'"
                if glob:
                    msg += f" (filter: {glob})"
                return msg

            else:
                # 错误
                error_msg = result.stderr.strip()
                return f"Error: ripgrep failed with code {result.returncode}\n{error_msg}"

        except subprocess.TimeoutExpired:
            return "Error: Search timed out (>30 seconds)"
        except Exception as e:
            return f"Error: {str(e)}"


# ============================================
# 使用示例
# ============================================

if __name__ == "__main__":
    print("=" * 70)
    print("Grep Tool Test")
    print("=" * 70)

    tool = GrepTool()

    # 检查 ripgrep 是否可用
    if not tool.rg_available:
        print("\nError: ripgrep is not available!")
        print("Please install ripgrep: https://github.com/BurntSushi/ripgrep")
        exit(1)

    # 测试 1: 查找包含 "Agent" 的文件
    print("\nTest 1: Find files containing 'Agent'\n")
    result = tool.execute(pattern="Agent", path="agent", output_mode="files_with_matches")
    print(result)

    # 测试 2: 显示匹配内容
    print("\n\nTest 2: Show matching content for 'class.*Tool'\n")
    result = tool.execute(
        pattern="class.*Tool",
        path="agent/tools",
        glob="*.py",
        output_mode="content",
        show_line_numbers=True
    )
    print(result[:1000])  # 只显示前 1000 字符

    # 测试 3: 计数
    print("\n\nTest 3: Count matches for 'def '\n")
    result = tool.execute(
        pattern="def ",
        path="agent",
        glob="*.py",
        output_mode="count"
    )
    print(result)

    # 测试 4: 忽略大小写
    print("\n\nTest 4: Case-insensitive search for 'AGENT'\n")
    result = tool.execute(
        pattern="AGENT",
        path="agent",
        case_insensitive=True,
        output_mode="files_with_matches"
    )
    print(result)
