from __future__ import annotations

from pathlib import Path
from agent.core.sandbox_types import AccessAction, SandboxDecision, SandboxZone


def classify_path(path: Path | None, *, workspace_root: Path, project_root: Path) -> SandboxZone:
    if path is None:
        return "unknown"

    resolved = path.resolve()
    workspace_root = Path(workspace_root).resolve()
    if _is_relative_to(resolved, workspace_root):
        return "workspace"

    project_root = Path(project_root).resolve()
    if _is_relative_to(resolved, project_root):
        return "project"

    return "outside"


def decide_path_access(
    path: Path | None,
    *,
    action: AccessAction,
    workspace_root: Path,
    project_root: Path,
    auto_mode: bool = False,
) -> tuple[SandboxDecision, SandboxZone]:
    zone = classify_path(path, workspace_root=workspace_root, project_root=project_root)

    if zone == "unknown" or action == "unknown":
        return "deny", zone

    if zone == "workspace":
        return "allow", zone

    if zone == "project":
        if action == "read":
            return "allow", zone
        if action in {"write", "delete"}:
            if auto_mode and _is_auto_writable_project_path(path, project_root):
                return "allow", zone
            return "ask", zone

    return "deny", zone


def _is_auto_writable_project_path(path: Path | None, project_root: Path) -> bool:
    if path is None:
        return False
    resolved = Path(path).resolve()
    project_root = Path(project_root).resolve()
    if not _is_relative_to(resolved, project_root):
        return False
    relative = resolved.relative_to(project_root)
    parts = relative.parts
    if not parts:
        return False
    if _is_core_or_agent_runtime_path(parts):
        return False
    if parts[0] in {"skills", "temp", "cache", "tools", ".venv"}:
        return True
    return parts == ("config", "runtime_env.local.json")


def _is_core_or_agent_runtime_path(parts: tuple[str, ...]) -> bool:
    if not parts:
        return False
    if parts[0] != "agent":
        return False
    if len(parts) == 1:
        return True
    if parts[1] == "core":
        return True
    if parts[1] == "tools":
        return True
    return parts[1] in {"agent_loop.py", "sandbox_guard.py", "permission_manager.py"}


def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False
