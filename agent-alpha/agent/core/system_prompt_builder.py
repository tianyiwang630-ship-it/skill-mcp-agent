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
    session_root: Path,
    input_dir: Path,
    output_dir: Path,
    temp_dir: Path,
    logs_dir: Path,
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

    return f"""You are an agent running inside agent-alpha.

## Runtime Paths
{task_line}
Workspace root: {workspace_root}
Session root: {session_root}
Session input directory: {input_dir}
Session output directory: {output_dir}
Session temp directory: {temp_dir}
Logs directory: {logs_dir}

## Project Resources
Skills root: {skills_dir}
MCP servers root: {mcp_servers_dir}
MCP registry: {mcp_registry_path}

## Workspace Rules
- Read task inputs from the session input directory first.
- Write final deliverables to the session output directory unless the user asks otherwise.
- Use the session temp directory for intermediate files and scratch outputs.
- Session-specific rules and persona can be provided through AGENTS.md and SOUL.md in the session input directory.
- Skill bodies are loaded on demand with `load_skill`; do not assume a skill's full content before loading it.

## Skills
Skills available:
{skills_section}

{prompt_docs_section}

## Large File Strategy
- For large outputs, prefer writing a complete file first and appending follow-up sections if needed.
- Use temp files for drafts or multi-step transformations before producing the final result.
"""
