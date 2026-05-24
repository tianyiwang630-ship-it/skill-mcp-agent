"""
Load optional prompt documents from the workspace root.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List


PROMPT_DOC_NAMES = ("AGENTS.md", "SOUL.md")


def load_workspace_prompt_documents(workspace_root: Path | str) -> List[Dict[str, str]]:
    """Load AGENTS.md and SOUL.md from the workspace root only."""
    workspace_root = Path(workspace_root).resolve()
    documents: List[Dict[str, str]] = []

    for name in PROMPT_DOC_NAMES:
        file_path = workspace_root / name
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
