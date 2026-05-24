"""
Utilities for constructing the agent system prompt.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional


def _build_skill_lines(skill_summaries: Optional[List[Dict[str, str]]]) -> str:
    lines = []
    for skill in skill_summaries or []:
        line = f"- {skill['name']}: {skill['description']}"
        if skill.get("path"):
            line += f" ({skill['path']})"
        lines.append(line)
    return "\n".join(lines) if lines else "(no skills available)"


def _build_prompt_documents_section(prompt_documents: Optional[List[Dict[str, str]]]) -> str:
    docs = prompt_documents or []
    if not docs:
        return "## Session Documents\nNo session-specific prompt documents were provided."

    parts = ["## Session Documents"]
    for doc in docs:
        parts.extend(
            [
                f"### {doc['name']}",
                f"Path: {doc['path']}",
                doc["content"],
                "",
            ]
        )
    return "\n".join(parts).strip()


def build_system_prompt(
    *,
    workspace_root: Path,
    logs_dir: Path | None,
    skills_dir: Path,
    mcp_servers_dir: Path,
    mcp_registry_path: Path,
    task_id: Optional[str] = None,
    skill_summaries: Optional[List[Dict[str, str]]] = None,
    prompt_documents: Optional[List[Dict[str, str]]] = None,
) -> str:
    """Build the base system prompt with runtime paths and optional session docs."""
    task_line = f"Task ID: {task_id}" if task_id else "Task ID: (not set)"
    skills_section = _build_skill_lines(skill_summaries)
    prompt_docs_section = _build_prompt_documents_section(prompt_documents)
    logs_line = str(logs_dir) if logs_dir else "(not provided by runner)"

    return f"""You are an agent running inside agent-alpha.

## Workspace
{task_line}
Workspace root: {workspace_root}

## System Resource Paths
Skills directory: {skills_dir}
MCP servers directory: {mcp_servers_dir}
MCP registry: {mcp_registry_path}

## Runtime Records
Logs directory: {logs_line}

## Workspace Rules
- AGENTS.md and SOUL.md are only loaded from the workspace root.
- Do not scan nested folders for AGENTS.md or SOUL.md.
- This workspace is the agent instance's dedicated workspace. It may contain persona docs, private reference materials, and active work files.
- The user may reference other folders by explicit paths in the conversation.
- Skill bodies are loaded on demand with `load_skill`; do not assume a skill's full content before loading it.
- System resource paths are primarily for reading and reference. Modify `skills` or `mcp-servers` only when the task explicitly requires maintaining those resources.
- Update the MCP registry only when MCP registration or categorization truly needs to change.
- Logs are runtime records, not the default place for normal task outputs.

## Skills
Skills available:
{skills_section}

{prompt_docs_section}

## Large File Strategy
- For large outputs, prefer writing a complete file first and appending follow-up sections if needed.
- When the user does not specify a target directory, choose the most appropriate workspace based on the task context and AGENTS.md guidance.
"""
