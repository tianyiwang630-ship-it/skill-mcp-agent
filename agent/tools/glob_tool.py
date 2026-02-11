"""
Glob Tool - 使用模式匹配查找文件
"""

import os
from pathlib import Path
from typing import Dict, Any, List

from agent.tools.base_tool import BaseTool


class GlobTool(BaseTool):
    """文件模式匹配工具"""

    @property
    def name(self) -> str:
        return "glob"

    def get_tool_definition(self) -> Dict[str, Any]:
        """
        返回 OpenAI function calling 格式的工具定义

        Returns:
            工具定义（OpenAI format）
        """
        return {
            "type": "function",
            "function": {
                "name": "glob",
                "description": "使用模式匹配查找文件。支持标准 glob 语法：* (任意字符), ** (递归目录), ? (单个字符), {a,b} (多选一), [abc] (字符集)。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "Glob 模式，如 '**/*.py' (所有 Python 文件), 'src/**/*.{js,ts}' (src 下所有 JS/TS 文件)"
                        },
                        "path": {
                            "type": "string",
                            "description": "搜索目录（可选，默认为当前工作目录）"
                        }
                    },
                    "required": ["pattern"]
                }
            }
        }

    def execute(self, **kwargs) -> str:
        """
        执行文件查找

        Args (via kwargs):
            pattern: Glob 模式
            path: 搜索目录（可选）

        Returns:
            匹配的文件列表（每行一个文件路径）
        """
        pattern = kwargs.get('pattern', '')
        path = kwargs.get('path')
        try:
            # 确定搜索根目录
            if path:
                root = Path(path)
                if not root.exists():
                    return f"Error: Directory does not exist: {path}"
                if not root.is_dir():
                    return f"Error: Not a directory: {path}"
            else:
                root = Path.cwd()

            # 执行 glob 查找
            # 使用 rglob 如果模式以 ** 开头
            if pattern.startswith('**/'):
                # 递归查找
                matches = list(root.rglob(pattern[3:]))
            elif '**' in pattern:
                # 包含 ** 的复杂模式
                matches = list(root.glob(pattern))
            else:
                # 简单模式
                matches = list(root.glob(pattern))

            # 过滤掉目录，只保留文件
            file_matches = [m for m in matches if m.is_file()]

            # 按修改时间排序（最新的在前）
            file_matches.sort(key=lambda x: x.stat().st_mtime, reverse=True)

            # 如果没有匹配
            if not file_matches:
                return f"No files found matching pattern: {pattern}" + (f" in {path}" if path else "")

            # 格式化输出
            # 使用相对于 root 的路径
            result_lines = []
            for file_path in file_matches:
                try:
                    relative_path = file_path.relative_to(root)
                    result_lines.append(str(relative_path).replace('\\', '/'))
                except ValueError:
                    # 如果无法计算相对路径，使用绝对路径
                    result_lines.append(str(file_path).replace('\\', '/'))

            # 添加头部信息
            header = f"# Found {len(result_lines)} file(s) matching '{pattern}'"
            if path:
                header += f" in '{path}'"
            header += f"\n# Sorted by modification time (newest first)\n"

            return header + "\n".join(result_lines)

        except Exception as e:
            return f"Error: {str(e)}"


# ============================================
# 使用示例
# ============================================

if __name__ == "__main__":
    print("=" * 70)
    print("Glob Tool Test")
    print("=" * 70)

    tool = GlobTool()

    # 测试 1: 查找所有 Python 文件
    print("\nTest 1: Find all Python files in agent/\n")
    result = tool.execute(pattern="**/*.py", path="agent")
    print(result)

    # 测试 2: 查找 core 目录的 Python 文件
    print("\n\nTest 2: Find Python files in agent/core/\n")
    result = tool.execute(pattern="*.py", path="agent/core")
    print(result)

    # 测试 3: 不存在的目录
    print("\n\nTest 3: Search in non-existent directory\n")
    result = tool.execute(pattern="*.py", path="nonexistent")
    print(result)

    # 测试 4: 没有匹配的文件
    print("\n\nTest 4: No matching files\n")
    result = tool.execute(pattern="*.xyz")
    print(result)
