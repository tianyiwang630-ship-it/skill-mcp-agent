"""
Edit Tool - 在文件中进行精确字符串替换
"""

from pathlib import Path
from typing import Dict, Any

from agent.tools.base_tool import BaseTool


class EditTool(BaseTool):
    """文件编辑工具 - 精确字符串替换"""

    @property
    def name(self) -> str:
        return "edit"

    def get_tool_definition(self) -> Dict[str, Any]:
        """
        返回 OpenAI function calling 格式的工具定义

        Returns:
            工具定义（OpenAI format）
        """
        return {
            "type": "function",
            "function": {
                "name": "edit",
                "description": "在文件中进行精确字符串替换。使用精确匹配（非正则），支持替换单个或所有匹配。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "要编辑的文件路径（绝对路径或相对路径）"
                        },
                        "old_string": {
                            "type": "string",
                            "description": "要替换的字符串（精确匹配）。当 replace_all=false 时，此字符串必须在文件中唯一。"
                        },
                        "new_string": {
                            "type": "string",
                            "description": "替换后的字符串"
                        },
                        "replace_all": {
                            "type": "boolean",
                            "description": "是否替换所有匹配（默认 false，只替换唯一匹配）",
                            "default": False
                        }
                    },
                    "required": ["file_path", "old_string", "new_string"]
                }
            }
        }

    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        执行文件编辑

        Args (via kwargs):
            file_path: 文件路径
            old_string: 要替换的字符串
            new_string: 替换后的字符串
            replace_all: 是否替换所有匹配

        Returns:
            编辑结果
        """
        file_path = kwargs.get('file_path')
        old_string = kwargs.get('old_string', '')
        new_string = kwargs.get('new_string', '')
        replace_all = kwargs.get('replace_all', False)

        try:
            # 转换为 Path 对象
            path = Path(file_path)

            # 检查文件是否存在
            if not path.exists():
                return {
                    "success": False,
                    "error": f"File does not exist: {file_path}"
                }

            # 检查是否是文件
            if not path.is_file():
                return {
                    "success": False,
                    "error": f"Not a file: {file_path}"
                }

            # 读取文件内容
            try:
                content = path.read_text(encoding='utf-8')
                encoding = 'utf-8'
            except UnicodeDecodeError:
                # 尝试 gbk 编码
                try:
                    content = path.read_text(encoding='gbk')
                    encoding = 'gbk'
                except:
                    return {
                        "success": False,
                        "error": "Cannot decode file (tried utf-8 and gbk)"
                    }
            except PermissionError:
                return {
                    "success": False,
                    "error": f"Permission denied: {file_path}"
                }

            # 检查 old_string 是否存在
            if old_string not in content:
                return {
                    "success": False,
                    "error": f"String not found in file: '{old_string[:50]}{'...' if len(old_string) > 50 else ''}'"
                }

            # 计算匹配次数
            match_count = content.count(old_string)

            # 如果不是 replace_all，检查是否唯一
            if not replace_all and match_count > 1:
                return {
                    "success": False,
                    "error": f"String appears {match_count} times in file (not unique). Use replace_all=true to replace all occurrences."
                }

            # 执行替换
            if replace_all:
                new_content = content.replace(old_string, new_string)
                replacements = match_count
            else:
                # 只替换一次（第一次出现）
                new_content = content.replace(old_string, new_string, 1)
                replacements = 1

            # 写回文件（保留原编码）
            try:
                path.write_text(new_content, encoding=encoding)
            except PermissionError:
                return {
                    "success": False,
                    "error": f"Permission denied when writing: {file_path}"
                }

            return {
                "success": True,
                "replacements": replacements,
                "message": f"Replaced {replacements} occurrence(s) in {file_path}",
                "details": {
                    "file_path": str(path),
                    "old_length": len(content),
                    "new_length": len(new_content),
                    "diff": len(new_content) - len(content)
                }
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
    print("Edit Tool Test")
    print("=" * 70)

    tool = EditTool()

    # 准备测试文件
    test_content = """Hello World
This is a test file.
Hello World again.
The end.
"""

    test_file = Path("workspace/temp/test_edit.txt")
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text(test_content)
    print("\nTest file created with content:")
    print(test_content)

    # 测试 1: 替换唯一字符串
    print("\nTest 1: Replace unique string 'The end'\n")
    result = tool.execute(
        file_path="workspace/temp/test_edit.txt",
        old_string="The end.",
        new_string="Goodbye!"
    )
    print(result)

    # 测试 2: 尝试替换不唯一的字符串（应该失败）
    print("\n\nTest 2: Try to replace non-unique string 'Hello World'\n")
    result = tool.execute(
        file_path="workspace/temp/test_edit.txt",
        old_string="Hello World",
        new_string="Hi World"
    )
    print(result)

    # 测试 3: 使用 replace_all
    print("\n\nTest 3: Replace all occurrences with replace_all=true\n")
    result = tool.execute(
        file_path="workspace/temp/test_edit.txt",
        old_string="Hello World",
        new_string="Hi World",
        replace_all=True
    )
    print(result)

    # 测试 4: 替换不存在的字符串
    print("\n\nTest 4: Try to replace non-existent string\n")
    result = tool.execute(
        file_path="workspace/temp/test_edit.txt",
        old_string="NonExistent",
        new_string="Something"
    )
    print(result)

    # 验证最终内容
    print("\n\nFinal file content:\n")
    final_content = Path("workspace/temp/test_edit.txt").read_text()
    print(final_content)
