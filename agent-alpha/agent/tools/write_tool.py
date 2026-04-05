"""
Write Tool - 写入或覆盖文件
"""

import os
import tempfile
from pathlib import Path
from typing import Dict, Any

from agent.tools.base_tool import BaseTool


class WriteTool(BaseTool):
    """文件写入工具"""

    @property
    def name(self) -> str:
        return "write"

    def get_tool_definition(self) -> Dict[str, Any]:
        """
        返回 OpenAI function calling 格式的工具定义

        Returns:
            工具定义（OpenAI format）
        """
        return {
            "type": "function",
            "function": {
                "name": "write",
                "description": "写入或覆盖文件内容。支持创建新文件或完全覆盖已有文件。使用原子写入确保文件完整性。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "要写入的文件路径（绝对路径或相对路径）"
                        },
                        "content": {
                            "type": "string",
                            "description": "要写入的文件内容"
                        }
                    },
                    "required": ["file_path", "content"]
                }
            }
        }

    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        执行文件写入

        Args (via kwargs):
            file_path: 文件路径
            content: 文件内容

        Returns:
            写入结果
        """
        file_path = kwargs.get('file_path')
        content = kwargs.get('content', '')

        try:
            # 转换为 Path 对象
            path = Path(file_path)

            # 确保父目录存在
            path.parent.mkdir(parents=True, exist_ok=True)

            # 原子写入：先写到临时文件，然后 rename
            # 这样可以避免写入过程中出错导致文件损坏
            temp_fd, temp_path = tempfile.mkstemp(
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp"
            )

            try:
                # 写入临时文件
                with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                    f.write(content)

                # 原子性地替换目标文件
                temp_path_obj = Path(temp_path)
                temp_path_obj.replace(path)

                # 成功
                file_size = path.stat().st_size
                lines = content.count('\n') + (1 if content and not content.endswith('\n') else 0)

                return {
                    "success": True,
                    "message": f"File written: {file_path}",
                    "details": {
                        "file_path": str(path),
                        "size_bytes": file_size,
                        "lines": lines
                    }
                }

            except Exception as e:
                # 清理临时文件
                try:
                    Path(temp_path).unlink()
                except:
                    pass
                raise e

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
    print("Write Tool Test")
    print("=" * 70)

    tool = WriteTool()

    # 测试 1: 创建新文件
    print("\nTest 1: Create new file\n")
    result = tool.execute(file_path="workspace/temp/test_write.txt", content="Hello, World!\nThis is a test file.\n")
    print(result)

    # 测试 2: 覆盖文件
    print("\n\nTest 2: Overwrite existing file\n")
    result = tool.execute(file_path="workspace/temp/test_write.txt", content="Overwritten content\n")
    print(result)

    # 测试 3: 创建多级目录
    print("\n\nTest 3: Create file with nested directories\n")
    result = tool.execute(file_path="workspace/temp/deep/nested/file.txt", content="Deep file\n")
    print(result)

    # 测试 4: 写入空内容
    print("\n\nTest 4: Write empty file\n")
    result = tool.execute(file_path="workspace/temp/empty.txt", content="")
    print(result)

    # 验证文件内容
    print("\n\nVerification: Read back the file\n")
    from pathlib import Path
    content = Path("workspace/temp/test_write.txt").read_text()
    print(f"File content:\n{content}")
