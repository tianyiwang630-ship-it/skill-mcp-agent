from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any, Dict

from agent.core.command_path_extractor import (
    classify_bash_command,
    explain_parseable_mutation_forms,
    extract_bash_paths,
    extract_script_path,
    split_bash_segments,
)
from agent.core.path_policy import decide_path_access
from agent.core.sandbox_types import AccessAction, SandboxCheckResult


class SandboxGuard:
    FILE_TOOL_ACTIONS: dict[str, AccessAction] = {
        "read": "read",
        "write": "write",
        "append": "write",
        "edit": "write",
    }

    def __init__(self, *, project_root: Path, workspace_root: Path):
        self.project_root = Path(project_root).resolve()
        self.workspace_root = Path(workspace_root).resolve()

    def check_tool_call(self, tool_name: str, arguments: Dict[str, Any], *, auto_mode: bool = False) -> SandboxCheckResult:
        if tool_name == "bash":
            return self._check_bash_command(arguments.get("command", ""), auto_mode=auto_mode)

        if tool_name not in self.FILE_TOOL_ACTIONS:
            return SandboxCheckResult(
                decision="allow",
                action="unknown",
                zone="unknown",
                reason="Sandbox not applied to this tool in phase 1",
            )

        action = self.FILE_TOOL_ACTIONS[tool_name]
        target_path = self._extract_path(arguments)
        decision, zone = decide_path_access(
            target_path,
            action=action,
            workspace_root=self.workspace_root,
            project_root=self.project_root,
            auto_mode=auto_mode,
        )

        if target_path is None:
            reason = "Could not determine the target path for this operation"
        elif zone == "workspace":
            reason = "Target path is inside an allowed workspace"
        elif zone == "project":
            if decision == "allow":
                reason = "Read access is allowed inside the agent-alpha project"
            else:
                reason = "Write access inside the agent-alpha project but outside the workspace requires user approval"
        elif zone == "outside":
            reason = "Target path is outside both the agent workspace and the agent-alpha project"
        else:
            reason = "Target path could not be classified safely"

        return SandboxCheckResult(
            decision=decision,
            action=action,
            zone=zone,
            reason=reason,
        )

    def _check_bash_command(self, command: str, *, auto_mode: bool = False) -> SandboxCheckResult:
        segments = split_bash_segments(command)
        if segments is None:
            return SandboxCheckResult(
                decision="deny",
                action="unknown",
                zone="unknown",
                reason="Shell command substitution or malformed command chaining is not allowed",
                guidance="Use simple chained commands with &&, ||, or ; only when each command is safe on its own.",
            )
        if len(segments) > 1:
            return self._check_bash_segments(segments, auto_mode=auto_mode)
        return self._check_single_bash_command(command, auto_mode=auto_mode)

    def _check_bash_segments(self, segments: list[str], *, auto_mode: bool = False) -> SandboxCheckResult:
        results = [self._check_single_bash_command(segment, auto_mode=auto_mode) for segment in segments]
        denied = next((result for result in results if result.decision == "deny"), None)
        if denied:
            return denied

        asks = [result for result in results if result.decision == "ask"]
        if asks:
            action: AccessAction = "write" if any(result.action in {"write", "delete"} for result in asks) else "unknown"
            return SandboxCheckResult(
                decision="ask",
                action=action,
                zone="project",
                reason="One or more chained bash commands require user approval",
                guidance="Review the full chained command before allowing it.",
            )

        return SandboxCheckResult(
            decision="allow",
            action="read",
            zone="unknown",
            reason="All chained bash commands are read-only or diagnostic commands",
        )

    def _check_single_bash_command(self, command: str, *, auto_mode: bool = False) -> SandboxCheckResult:
        category = classify_bash_command(command)

        if category == "dangerous":
            return SandboxCheckResult(
                decision="deny",
                action="unknown",
                zone="unknown",
                reason="Dangerous system-level bash commands are not allowed",
                guidance="Disallowed examples include sudo, format, mkfs, diskpart, shutdown, reboot, and destructive permission changes.",
            )

        if category == "package_install":
            if auto_mode and _is_auto_python_install(command):
                return SandboxCheckResult(
                    decision="allow",
                    action="write",
                    zone="project",
                    reason="Python package installation is allowed in auto mode for the agent-alpha runtime",
                )
            return SandboxCheckResult(
                decision="ask",
                action="write",
                zone="project",
                reason="Package installation or removal commands require user approval",
                guidance="Package installation commands such as pip install or npm install are allowed only after one-time approval.",
            )

        if category == "project_command":
            return SandboxCheckResult(
                decision="allow",
                action="read",
                zone="project",
                reason="Project command execution is allowed for common development workflows",
            )

        lowered_command = command.strip().lower()
        if lowered_command in {"git checkout -- .", "git restore ."}:
            return SandboxCheckResult(
                decision="ask",
                action="write",
                zone="project",
                reason="Bulk git restore commands require user approval",
                guidance="Single-file restore commands like git checkout -- file or git restore file can be parsed and sandboxed more precisely.",
            )

        if lowered_command.startswith("git apply "):
            return SandboxCheckResult(
                decision="allow",
                action="write",
                zone="project",
                reason="git apply is allowed for project patch workflows",
            )

        if category == "script_run":
            script_path = extract_script_path(command)
            decision, zone = decide_path_access(
                script_path,
                action="read",
                workspace_root=self.workspace_root,
                project_root=self.project_root,
                auto_mode=auto_mode,
            )
            if zone in {"workspace", "project"}:
                return SandboxCheckResult(
                    decision="allow",
                    action="read",
                    zone=zone,
                    reason="Script execution is allowed when the script file is inside a workspace or the agent-alpha project",
                )
            return SandboxCheckResult(
                decision="deny",
                action="read",
                zone=zone,
                reason="Script execution is allowed only for scripts inside an agent workspace or the agent-alpha project",
            )

        if category in {"read_only", "path_mutation"}:
            extracted = extract_bash_paths(command, category)
            if extracted is None:
                action: AccessAction = "write" if category == "path_mutation" else "read"
                return SandboxCheckResult(
                    decision="deny",
                    action=action,
                    zone="unknown",
                    reason="This bash command could not be parsed safely",
                    guidance=explain_parseable_mutation_forms() if category == "path_mutation" else "Use simple read-only commands with explicit paths when accessing files.",
                )

            action, paths = extracted
            if not paths:
                return SandboxCheckResult(
                    decision="allow",
                    action=action,
                    zone="unknown",
                    reason="Read-only bash command does not target a file path",
                )

            decisions = [
                decide_path_access(
                    path,
                    action=action,
                    workspace_root=self.workspace_root,
                    project_root=self.project_root,
                    auto_mode=auto_mode,
                )
                for path in paths
            ]

            if any(decision == "deny" for decision, _zone in decisions):
                return SandboxCheckResult(
                    decision="deny",
                    action=action,
                    zone=next(zone for decision, zone in decisions if decision == "deny"),
                    reason="The bash command targets a path outside the allowed workspace or project boundaries",
                    guidance=explain_parseable_mutation_forms() if category == "path_mutation" else None,
                )

            if any(decision == "ask" for decision, _zone in decisions):
                return SandboxCheckResult(
                    decision="ask",
                    action=action,
                    zone=next(zone for decision, zone in decisions if decision == "ask"),
                    reason="The bash command modifies files inside the agent-alpha project but outside the current workspace",
                    guidance=explain_parseable_mutation_forms() if category == "path_mutation" else None,
                )

            return SandboxCheckResult(
                decision="allow",
                action=action,
                zone=decisions[0][1],
                reason="The bash command targets only allowed paths",
            )

        return SandboxCheckResult(
            decision="ask",
            action="unknown",
            zone="unknown",
            reason="This bash command is not recognized as read-only, an install command, or a known dangerous command",
            guidance="Unknown commands require user approval. Prefer simple single commands so the sandbox can classify them.",
        )

    def _extract_path(self, arguments: Dict[str, Any]) -> Path | None:
        raw_path = arguments.get("file_path")
        if not raw_path:
            return None
        try:
            return Path(raw_path).resolve()
        except Exception:
            return None


def _is_auto_python_install(command: str) -> bool:
    try:
        tokens = [token.lower() for token in shlex.split(command, posix=False)]
    except ValueError:
        return False
    if len(tokens) >= 3 and tokens[:3] == ["uv", "pip", "install"]:
        return True
    if len(tokens) >= 2 and tokens[:2] == ["pip", "install"]:
        return True
    return len(tokens) >= 4 and tokens[0] in {"python", "python3", "py"} and tokens[1:4] == ["-m", "pip", "install"]
