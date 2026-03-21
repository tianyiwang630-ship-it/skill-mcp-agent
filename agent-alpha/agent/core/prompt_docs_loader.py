"""
Load optional prompt documents from the current session input directory.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List


PROMPT_DOC_NAMES = ("AGENTS.md", "SOUL.md")


def load_session_prompt_documents(session_input_dir: Path) -> List[Dict[str, str]]:
    """Load supported prompt documents from the session input directory."""
    input_dir = Path(session_input_dir)
    documents: List[Dict[str, str]] = []

    for name in PROMPT_DOC_NAMES:
        file_path = input_dir / name
        if not file_path.exists():
            continue
        documents.append(
            {
                "name": name,
                "path": str(file_path.resolve()),
                "content": file_path.read_text(encoding="utf-8").strip(),
            }
        )

    return documents
