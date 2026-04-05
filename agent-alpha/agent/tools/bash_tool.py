"""
Bash Tool - 像 Claude Code 一样执行 bash 命令
"""

import subprocess
import platform
from typing import Dict, Any, List

from agent.tools.base_tool import BaseTool


class BashTool(BaseTool):
    """Bash 命令执行工具"""

    @property
    def name(self) -> str:
        return "bash"

    def __init__(self, timeout: int = 300):
        """
        初始化 Bash Tool

        Args:
            timeout: 命令超时时间（秒，默认 300 秒 = 5 分钟）
        """
        self.timeout = timeout
        self._detect_shell()

    def _detect_shell(self):
        """检测可用的 shell"""
        system = platform.system()

        if system == "Windows":
            # Windows 上的优先级：Git Bash（多种路径） > WSL > cmd

            # Git Bash 的常见安装路径
            git_bash_paths = [
                r"C:\Program Files\Git\bin\bash.exe",
                r"C:\Program Files (x86)\Git\bin\bash.exe",
                "bash",  # 如果在 PATH 中
            ]

            # 尝试 Git Bash
            for bash_path in git_bash_paths:
                try:
                    result = subprocess.run(
                        [bash_path, "-c", "echo test"],
                        capture_output=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        self.shell = bash_path
                        shell_name = "Git Bash" if "Program Files" in bash_path else "bash"
                        print(f"✅ 检测到 shell: {shell_name}")
                        return
                except:
                    continue

            # 尝试 WSL
            try:
                result = subprocess.run(
                    ["wsl", "bash", "-c", "echo test"],
                    capture_output=True,
                    timeout=5
                )
                if result.returncode == 0:
                    self.shell = "wsl"
                    print(f"✅ 检测到 shell: WSL")
                    return
            except:
                pass

            # 默认 cmd
            self.shell = "cmd"
            print(f"⚠️  未找到 bash/WSL，使用默认 shell: cmd")

        else:
            # Linux/Mac 使用 bash
            self.shell = "bash"
            print(f"✅ 使用 shell: bash")

    def get_tool_definition(self) -> Dict[str, Any]:
        """
        返回 OpenAI function calling 格式的工具定义

        Returns:
            工具定义
        """
        return {
            "type": "function",
            "function": {
                "name": "bash",
                "description": "执行 bash/shell 命令并返回结果。可以运行任何命令行程序。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "要执行的命令（例如：ls -la, cat file.txt, python script.py）"
                        }
                    },
                    "required": ["command"]
                }
            }
        }

    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        执行命令

        Args (via kwargs):
            command: 要执行的命令

        Returns:
            执行结果
        """
        command = kwargs.get('command', '')

        try:
            # 根据 shell 类型调整命令格式
            if self.shell == "cmd":
                cmd_args = ["cmd", "/c", command]
            elif self.shell == "wsl":
                cmd_args = ["wsl", "bash", "-c", command]
            elif self.shell.endswith(".exe") or "\\" in self.shell:
                # Git Bash 完整路径
                cmd_args = [self.shell, "-c", command]
            else:
                # 普通 bash
                cmd_args = ["bash", "-c", command]

            # 执行命令
            result = subprocess.run(
                cmd_args,
                capture_output=True,
                text=True,
                encoding='utf-8',  # 明确使用UTF-8编码，避免Windows GBK编码问题
                errors='replace',  # 遇到无法解码的字符用�替换，而不是抛出异常
                timeout=self.timeout,
                cwd=None  # 使用当前工作目录
            )

            # 限制输出长度，避免占用过多 tokens
            # Claude Code 使用 50,000 字符，我们对齐这个限制
            max_output_length = 50000  # 最多 50000 字符
            stdout = result.stdout
            stderr = result.stderr

            if stdout and len(stdout) > max_output_length:
                stdout = stdout[:max_output_length] + f"\n... (输出过长，已截断，总长度: {len(result.stdout)} 字符)"

            if stderr and len(stderr) > max_output_length:
                stderr = stderr[:max_output_length] + f"\n... (错误输出过长，已截断)"

            return {
                "success": result.returncode == 0,
                "stdout": stdout,
                "stderr": stderr,
                "returncode": result.returncode,
                "command": command
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"命令超时（>{self.timeout}秒）",
                "command": command
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "command": command
            }


# ============================================
# 使用示例
# ============================================

if __name__ == "__main__":
    print("=" * 60)
    print("Bash Tool 测试")
    print("=" * 60)

    # 初始化
    bash = BashTool()

    # 测试命令
    test_commands = [
        "echo 'Hello from Bash!'",
        "ls -la",
        "pwd",
        "python --version"
    ]

    for cmd in test_commands:
        print(f"\n📝 命令: {cmd}")
        result = bash.execute(command=cmd)

        if result.get("success"):
            print(f"✅ 成功")
            print(f"输出:\n{result['stdout']}")
        else:
            print(f"❌ 失败")
            if "error" in result:
                print(f"错误: {result['error']}")
            if result.get("stderr"):
                print(f"stderr:\n{result['stderr']}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
