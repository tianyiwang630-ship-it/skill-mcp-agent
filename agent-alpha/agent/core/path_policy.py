from __future__ import annotations

from pathlib import Path
from typing import Iterable

from agent.core.sandbox_types import AccessAction, SandboxDecision, SandboxZone


def classify_path(path: Path | None, *, workspaces: Iterable[Path], project_root: Path) -> SandboxZone:
    if path is None:
        return "unknown"

    resolved = path.resolve()
    workspace_roots = [Path(workspace).resolve() for workspace in workspaces]
    for workspace in workspace_roots:
        if _is_relative_to(resolved, workspace):
            return "workspace"

    project_root = Path(project_root).resolve()
    if _is_relative_to(resolved, project_root):
        return "project"

    return "outside"


def decide_path_access(
    path: Path | None,
    *,
    action: AccessAction,
    workspaces: Iterable[Path],
    project_root: Path,
) -> tuple[SandboxDecision, SandboxZone]:
    zone = classify_path(path, workspaces=workspaces, project_root=project_root)

    if zone == "unknown" or action == "unknown":
        return "deny", zone

    if zone == "workspace":
        return "allow", zone

    if zone == "project":
        if action == "read":
            return "allow", zone
        if action in {"write", "delete"}:
            return "ask", zone

    return "deny", zone


def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False
