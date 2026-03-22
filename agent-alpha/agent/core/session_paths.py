"""
Workspace and CLI session layout helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AgentWorkspacePaths:
    workspace_root: Path
    input_dir: Path
    output_dir: Path
    temp_dir: Path


@dataclass(frozen=True)
class CliSessionPaths:
    session_root: Path
    logs_dir: Path
    workspace_paths: AgentWorkspacePaths


def ensure_agent_workspace(workspace_root: Path) -> AgentWorkspacePaths:
    """Ensure an agent workspace contains input/output/temp directories."""
    root = Path(workspace_root).resolve()
    input_dir = root / "input"
    output_dir = root / "output"
    temp_dir = root / "temp"

    for directory in (input_dir, output_dir, temp_dir):
        directory.mkdir(parents=True, exist_ok=True)

    return AgentWorkspacePaths(
        workspace_root=root,
        input_dir=input_dir.resolve(),
        output_dir=output_dir.resolve(),
        temp_dir=temp_dir.resolve(),
    )


def create_cli_session_paths(*, workspace_root: Path, session_id: str) -> CliSessionPaths:
    """Create one CLI session workspace plus the shared logs directory."""
    root = Path(workspace_root).resolve()
    session_root = root / "sessions" / session_id
    logs_dir = root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    return CliSessionPaths(
        session_root=session_root.resolve(),
        logs_dir=logs_dir.resolve(),
        workspace_paths=ensure_agent_workspace(session_root),
    )
