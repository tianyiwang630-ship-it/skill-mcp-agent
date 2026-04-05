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
    private_workspace: Path,
    additional_workspaces: Optional[List[Path]] = None,
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
    additional_workspace_lines = "\n".join(
        f"- {path}" for path in (additional_workspaces or [])
    ) or "(none)"

    return f"""You are an agent running inside agent-alpha.

## Private Workspace
{task_line}
Primary workspace: {private_workspace}

## Additional Workspaces
{additional_workspace_lines}

## System Resource Paths
Skills directory: {skills_dir}
MCP servers directory: {mcp_servers_dir}
MCP registry: {mcp_registry_path}

## Runtime Records
Logs directory: {logs_line}

## Workspace Rules
- AGENTS.md and SOUL.md are only loaded from the private workspace root.
- Do not scan nested folders for AGENTS.md or SOUL.md.
- The private workspace is this agent's dedicated workspace. It may contain persona docs, private reference materials, and active work files.
- Additional workspaces may also contain files that this agent needs to read or modify.
- If multiple workspaces are provided, their roles should be interpreted from AGENTS.md.
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
