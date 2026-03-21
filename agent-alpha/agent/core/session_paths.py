"""
Session workspace layout helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SessionPaths:
    workspace_root: Path
    sessions_dir: Path
    session_root: Path
    input_dir: Path
    output_dir: Path
    temp_dir: Path
    logs_dir: Path


def create_session_paths(*, workspace_root: Path, session_id: str) -> SessionPaths:
    """Create and return the directory layout for one agent session."""
    root = Path(workspace_root).resolve()
    sessions_dir = root / "sessions"
    session_root = sessions_dir / session_id
    input_dir = session_root / "input"
    output_dir = session_root / "output"
    temp_dir = session_root / "temp"
    logs_dir = root / "logs"

    for directory in (input_dir, output_dir, temp_dir, logs_dir):
        directory.mkdir(parents=True, exist_ok=True)

    return SessionPaths(
        workspace_root=root,
        sessions_dir=sessions_dir.resolve(),
        session_root=session_root.resolve(),
        input_dir=input_dir.resolve(),
        output_dir=output_dir.resolve(),
        temp_dir=temp_dir.resolve(),
        logs_dir=logs_dir.resolve(),
    )
