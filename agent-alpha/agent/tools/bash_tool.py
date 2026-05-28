"""Shell command execution tool."""

from __future__ import annotations

import platform
import subprocess
from pathlib import Path
from typing import Any, Dict

from agent.core.runtime_env import redact_secrets, subprocess_env
from agent.tools.base_tool import BaseTool


class BashTool(BaseTool):
    """Execute shell commands and return captured output."""

    @property
    def name(self) -> str:
        return "bash"

    def __init__(self, timeout: int = 300, project_root: Path | None = None):
        self.timeout = timeout
        self.project_root = Path(project_root).resolve() if project_root else Path(__file__).resolve().parents[2]
        self._detect_shell()

    def _detect_shell(self) -> None:
        system = platform.system()

        if system == "Windows":
            for powershell_path in ["powershell", "pwsh"]:
                try:
                    result = subprocess.run(
                        [powershell_path, "-NoProfile", "-Command", "Write-Output test"],
                        capture_output=True,
                        timeout=5,
                    )
                    if result.returncode == 0:
                        self.shell = powershell_path
                        print("OK detected shell: PowerShell")
                        return
                except Exception:
                    continue

            for bash_path in [
                r"C:\Program Files\Git\bin\bash.exe",
                r"C:\Program Files (x86)\Git\bin\bash.exe",
                "bash",
            ]:
                try:
                    result = subprocess.run(
                        [bash_path, "-c", "echo test"],
                        capture_output=True,
                        timeout=5,
                    )
                    if result.returncode == 0:
                        self.shell = bash_path
                        shell_name = "Git Bash" if "Program Files" in bash_path else "bash"
                        print(f"OK detected shell: {shell_name}")
                        return
                except Exception:
                    continue

            try:
                result = subprocess.run(
                    ["wsl", "bash", "-c", "echo test"],
                    capture_output=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    self.shell = "wsl"
                    print("OK detected shell: WSL")
                    return
            except Exception:
                pass

            self.shell = "cmd"
            print("Warning: no PowerShell, Git Bash, or WSL found; using cmd")
            return

        self.shell = "bash"
        print("OK using shell: bash")

    def get_tool_definition(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "bash",
                "description": (
                    "Execute a shell command and return the result. "
                    "On Windows this uses PowerShell by default."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "The shell command to execute.",
                        }
                    },
                    "required": ["command"],
                },
            },
        }

    def execute(self, **kwargs) -> Dict[str, Any]:
        command = kwargs.get("command", "")

        try:
            if self.shell == "cmd":
                cmd_args = ["cmd", "/c", command]
            elif self.shell in {"powershell", "pwsh"}:
                cmd_args = [self.shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command]
            elif self.shell == "wsl":
                cmd_args = ["wsl", "bash", "-c", command]
            elif self.shell.endswith(".exe") or "\\" in self.shell:
                cmd_args = [self.shell, "-c", command]
            else:
                cmd_args = ["bash", "-c", command]

            result = subprocess.run(
                cmd_args,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout,
                cwd=None,
                env=subprocess_env(self.project_root),
            )

            max_output_length = 50000
            stdout = result.stdout
            stderr = result.stderr

            if stdout and len(stdout) > max_output_length:
                stdout = stdout[:max_output_length] + f"\n... (output truncated, total {len(result.stdout)} chars)"

            if stderr and len(stderr) > max_output_length:
                stderr = stderr[:max_output_length] + "\n... (stderr truncated)"

            return {
                "success": result.returncode == 0,
                "stdout": redact_secrets(stdout, self.project_root),
                "stderr": redact_secrets(stderr, self.project_root),
                "returncode": result.returncode,
                "command": redact_secrets(command, self.project_root),
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"Command timed out after {self.timeout} seconds",
                "command": command,
            }

        except Exception as exc:
            return {
                "success": False,
                "error": str(exc),
                "command": command,
            }
