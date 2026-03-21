"""
Skill loader for two-layer skill disclosure.

Layer 1: parse metadata for system prompt summaries.
Layer 2: return the full skill body on demand via load_skill(name).
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Dict, List


class SkillLoader:
    """Scan skills/<name>/SKILL.md files and expose summaries/body lookups."""

    def __init__(self, skills_dir: Path):
        self.skills_dir = Path(skills_dir)
        self.skills: Dict[str, Dict[str, Any]] = {}
        self.reload()

    def reload(self) -> None:
        """Rescan skills from disk."""
        self.skills = {}
        if not self.skills_dir.exists():
            return

        for skill_file in sorted(self.skills_dir.rglob("SKILL.md")):
            meta, body = self._parse_skill_file(skill_file)
            name = meta.get("name") or skill_file.parent.name
            description = meta.get("description")
            if not name or not description:
                continue
            self.skills[name] = {
                "meta": meta,
                "body": body,
                "path": str(skill_file),
            }

    def get_summaries(self) -> List[Dict[str, str]]:
        """Return prompt-safe summaries for all skills."""
        summaries: List[Dict[str, str]] = []
        for name, skill in self.skills.items():
            meta = skill["meta"]
            summary = {
                "name": name,
                "description": meta["description"],
                "path": skill["path"],
            }
            if meta.get("tags"):
                summary["tags"] = meta["tags"]
            summaries.append(summary)
        return summaries

    def get_content(self, name: str) -> str:
        """Return the full skill body in tool_result-friendly markup."""
        skill = self.skills.get(name)
        if not skill:
            available = ", ".join(sorted(self.skills)) or "(none)"
            return f"Error: Unknown skill '{name}'. Available: {available}"
        return f'<skill name="{name}">\n{skill["body"]}\n</skill>'

    def _parse_skill_file(self, skill_file: Path) -> tuple[Dict[str, str], str]:
        text = skill_file.read_text(encoding="utf-8")
        match = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.DOTALL)
        if not match:
            return {}, text.strip()

        meta: Dict[str, str] = {}
        for line in match.group(1).splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()
        return meta, match.group(2).strip()
