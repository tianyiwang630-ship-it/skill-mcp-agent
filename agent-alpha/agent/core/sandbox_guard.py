from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable

from agent.core.command_path_extractor import (
    classify_bash_command,
    explain_parseable_mutation_forms,
    extract_bash_paths,
    extract_script_path,
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

    def __init__(self, *, project_root: Path, workspaces: Iterable[Path]):
        self.project_root = Path(project_root).resolve()
        self.workspaces = [Path(workspace).resolve() for workspace in workspaces]

    def check_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> SandboxCheckResult:
        if tool_name == "bash":
            return self._check_bash_command(arguments.get("command", ""))

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
            workspaces=self.workspaces,
            project_root=self.project_root,
        )

        if target_path is None:
            reason = "Could not determine the target path for this operation"
        elif zone == "workspace":
            reason = "Target path is inside an allowed workspace"
        elif zone == "project":
            if decision == "allow":
                reason = "Read access is allowed inside the agent-alpha project"
            else:
                reason = "Write access inside the agent-alpha project but outside workspaces requires user approval"
        elif zone == "outside":
            reason = "Target path is outside both the agent workspaces and the agent-alpha project"
        else:
            reason = "Target path could not be classified safely"

        return SandboxCheckResult(
            decision=decision,
            action=action,
            zone=zone,
            reason=reason,
        )

    def _check_bash_command(self, command: str) -> SandboxCheckResult:
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
                workspaces=self.workspaces,
                project_root=self.project_root,
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
                    workspaces=self.workspaces,
                    project_root=self.project_root,
                )
                for path in paths
            ]

            if any(decision == "deny" for decision, _zone in decisions):
                return SandboxCheckResult(
                    decision="deny",
                    action=action,
                    zone=next(zone for decision, zone in decisions if decision == "deny"),
                    reason="The bash command targets a path outside the allowed workspaces or project boundaries",
                    guidance=explain_parseable_mutation_forms() if category == "path_mutation" else None,
                )

            if any(decision == "ask" for decision, _zone in decisions):
                return SandboxCheckResult(
                    decision="ask",
                    action=action,
                    zone=next(zone for decision, zone in decisions if decision == "ask"),
                    reason="The bash command modifies files inside the agent-alpha project but outside the current workspaces",
                    guidance=explain_parseable_mutation_forms() if category == "path_mutation" else None,
                )

            return SandboxCheckResult(
                decision="allow",
                action=action,
                zone=decisions[0][1],
                reason="The bash command targets only allowed paths",
            )

        return SandboxCheckResult(
            decision="deny",
            action="unknown",
            zone="unknown",
            reason="This bash command is not in an allowed or safely parseable form",
            guidance=explain_parseable_mutation_forms(),
        )

    def _extract_path(self, arguments: Dict[str, Any]) -> Path | None:
        raw_path = arguments.get("file_path")
        if not raw_path:
            return None
        try:
            return Path(raw_path).resolve()
        except Exception:
            return None
