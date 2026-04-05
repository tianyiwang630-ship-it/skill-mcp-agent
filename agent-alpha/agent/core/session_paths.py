"""CLI session layout helpers."""

from __future__ import annotations

from pathlib import Path


def create_cli_session_paths(*, workspace_root: Path, session_id: str) -> tuple[Path, Path]:
    """Create one CLI session workspace plus the shared logs directory."""
    root = Path(workspace_root).resolve()
    session_root = root / "sessions" / session_id
    logs_dir = root / "logs"
    session_root.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    return session_root.resolve(), logs_dir.resolve()
