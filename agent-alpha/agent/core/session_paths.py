"""CLI session layout helpers."""

from __future__ import annotations

from pathlib import Path


def get_default_workspace_root(project_root: Path) -> Path:
    """Return the default shared workspace root for the CLI."""
    return (Path(project_root).resolve() / "workspace").resolve()


def create_cli_session_paths(*, project_root: Path) -> tuple[Path, Path]:
    """Create the session snapshot and log directories for the CLI."""
    root = Path(project_root).resolve()
    session_log_root = root / "session-log"
    sessions_dir = session_log_root / "sessions"
    logs_dir = session_log_root / "logs"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    return sessions_dir.resolve(), logs_dir.resolve()
