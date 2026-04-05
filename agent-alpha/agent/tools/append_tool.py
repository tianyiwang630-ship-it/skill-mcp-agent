"""
Append Tool - 追加内容到文件末尾
"""

from pathlib import Path
from typing import Dict, Any

from agent.tools.base_tool import BaseTool


class AppendTool(BaseTool):
    """文件追加工具"""

    @property
    def name(self) -> str:
        return "append"

    def get_tool_definition(self) -> Dict[str, Any]:
        """
        返回 OpenAI function calling 格式的工具定义

        Returns:
            工具定义（OpenAI format）
        """
        return {
            "type": "function",
            "function": {
                "name": "append",
                "description": "追加内容到文件末尾。如果文件不存在则创建新文件。用于分块写入大文件：先用 write 创建文件，再用 append 追加后续内容。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "要追加内容的文件路径（绝对路径或相对路径）"
                        },
                        "content": {
                            "type": "string",
                            "description": "要追加的内容"
                        }
                    },
                    "required": ["file_path", "content"]
                }
            }
        }

    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        执行文件追加

        Args (via kwargs):
            file_path: 文件路径
            content: 要追加的内容

        Returns:
            追加结果
        """
        file_path = kwargs.get('file_path')
        content = kwargs.get('content', '')
        try:
            path = Path(file_path)

            # 确保父目录存在
            path.parent.mkdir(parents=True, exist_ok=True)

            # 追加写入（如果文件不存在会自动创建）
            with open(path, 'a', encoding='utf-8') as f:
                f.write(content)

            # 统计信息
            file_size = path.stat().st_size
            lines = content.count('\n') + (1 if content and not content.endswith('\n') else 0)

            return {
                "success": True,
                "message": f"Content appended to: {file_path}",
                "details": {
                    "file_path": str(path),
                    "appended_bytes": len(content.encode('utf-8')),
                    "total_size_bytes": file_size,
                    "appended_lines": lines
                }
            }

        except PermissionError:
            return {
                "success": False,
                "error": f"Permission denied: {file_path}"
            }
        except OSError as e:
            return {
                "success": False,
                "error": f"OS error: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}"
            }


# ============================================
# 使用示例
# ============================================

if __name__ == "__main__":
    print("=" * 70)
    print("Append Tool Test")
    print("=" * 70)

    tool = AppendTool()

    # 测试 1: 创建新文件（通过追加）
    print("\nTest 1: Create new file via append\n")
    result = tool.execute(file_path="workspace/temp/test_append.txt", content="First line\n")
    print(result)

    # 测试 2: 追加内容
    print("\n\nTest 2: Append to existing file\n")
    result = tool.execute(file_path="workspace/temp/test_append.txt", content="Second line\n")
    print(result)

    # 测试 3: 追加中文内容
    print("\n\nTest 3: Append Chinese content\n")
    result = tool.execute(file_path="workspace/temp/test_append.txt", content="第三行：中文内容\n")
    print(result)

    # 验证文件内容
    print("\n\nVerification: Read back the file\n")
    content = Path("workspace/temp/test_append.txt").read_text(encoding='utf-8')
    print(f"File content:\n{content}")
