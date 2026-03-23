"""
Load optional prompt documents from the first workspace root.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List


PROMPT_DOC_NAMES = ("AGENTS.md", "SOUL.md")


def load_workspace_prompt_documents(workspaces: Iterable[Path | str]) -> List[Dict[str, str]]:
    """Load AGENTS.md and SOUL.md from the first workspace root only."""
    resolved_workspaces = [Path(workspace).resolve() for workspace in workspaces]
    if not resolved_workspaces:
        return []

    private_workspace = resolved_workspaces[0]
    documents: List[Dict[str, str]] = []

    for name in PROMPT_DOC_NAMES:
        file_path = private_workspace / name
        if not file_path.is_file():
            continue
        documents.append(
            {
                "name": name,
                "path": str(file_path),
                "content": file_path.read_text(encoding="utf-8").strip(),
            }
        )

    return documents
