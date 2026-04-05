"""
Read Tool - 读取文件内容，返回带行号的格式
"""

from pathlib import Path
from typing import Dict, Any

from agent.tools.base_tool import BaseTool


class ReadTool(BaseTool):
    """文件读取工具 - 类似 cat -n"""

    @property
    def name(self) -> str:
        return "read"

    def get_tool_definition(self) -> Dict[str, Any]:
        """
        返回 OpenAI function calling 格式的工具定义

        Returns:
            工具定义（OpenAI format）
        """
        return {
            "type": "function",
            "function": {
                "name": "read",
                "description": "读取文件内容，返回带行号的格式（类似 cat -n）。支持按行读取，可指定起始行和行数限制。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "要读取的文件的绝对路径或相对路径"
                        },
                        "offset": {
                            "type": "integer",
                            "description": "起始行号（从 0 开始，默认为 0）",
                            "default": 0
                        },
                        "limit": {
                            "type": "integer",
                            "description": "最多读取的行数（默认 2000 行）",
                            "default": 2000
                        }
                    },
                    "required": ["file_path"]
                }
            }
        }

    def execute(self, **kwargs) -> str:
        """
        执行文件读取

        Args (via kwargs):
            file_path: 文件路径
            offset: 起始行号（从 0 开始）
            limit: 最多读取的行数

        Returns:
            带行号的文件内容
        """
        file_path = kwargs.get('file_path')
        offset = kwargs.get('offset', 0) or 0
        limit = kwargs.get('limit', 2000) or 2000

        try:
            # 转换为 Path 对象
            path = Path(file_path)

            # 检查文件是否存在
            if not path.exists():
                return f"❌ 错误: 文件不存在: {file_path}"

            # 检查是否是文件（不是目录）
            if not path.is_file():
                return f"❌ 错误: 不是文件: {file_path}"

            # 读取文件内容
            try:
                content = path.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                # 尝试其他编码
                try:
                    content = path.read_text(encoding='gbk')
                except:
                    return f"❌ 错误: 无法解码文件（尝试了 utf-8 和 gbk）: {file_path}"
            except PermissionError:
                return f"❌ 错误: 没有权限读取文件: {file_path}"

            # 检查是否为空文件
            if not content:
                return f"⚠️  文件为空: {file_path}"

            # 分割成行
            lines = content.splitlines()

            # 应用 offset 和 limit
            total_lines = len(lines)
            start = offset
            end = min(offset + limit, total_lines)

            if start >= total_lines:
                return f"⚠️  起始行 {start} 超出文件范围（总共 {total_lines} 行）"

            selected_lines = lines[start:end]

            # 格式化输出（带行号，从 1 开始）
            # 格式: "     1→内容"
            max_line_num = start + len(selected_lines)
            num_width = len(str(max_line_num))

            result_lines = []
            for i, line in enumerate(selected_lines, start=start + 1):
                # 截断过长的行（最多 2000 字符）
                if len(line) > 2000:
                    line = line[:2000] + "... (行内容过长，已截断)"

                # 格式化行号
                line_num_str = str(i).rjust(num_width)
                result_lines.append(f"{line_num_str}→{line}")

            # 添加文件信息头
            header = f"# 文件: {file_path}\n# 显示: 第 {start + 1}-{end} 行 / 共 {total_lines} 行\n"

            # 如果有未显示的内容，添加提示
            footer = ""
            if end < total_lines:
                footer = f"\n\n... 还有 {total_lines - end} 行未显示（使用 offset={end} 继续读取）"

            return header + "\n".join(result_lines) + footer

        except Exception as e:
            return f"❌ 错误: {str(e)}"


# ============================================
# 使用示例
# ============================================

if __name__ == "__main__":
    print("=" * 70)
    print("Read Tool Test")
    print("=" * 70)

    tool = ReadTool()

    # 测试 1: 读取本文件前 20 行
    print("\nTest 1: Read first 20 lines of this file\n")
    result = tool.execute(file_path=__file__, offset=0, limit=20)
    print(result)

    # 测试 2: 读取不存在的文件
    print("\n\nTest 2: Read non-existent file\n")
    result = tool.execute(file_path="nonexistent_file.txt")
    print(result)

    # 测试 3: 使用 offset
    print("\n\nTest 3: Read 10 lines starting from line 10\n")
    result = tool.execute(file_path=__file__, offset=10, limit=10)
    print(result)
