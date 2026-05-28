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
    workspace_skills_dir: Path | None = None,
    runtime_python: Path | None = None,
    task_id: Optional[str] = None,
    skill_summaries: Optional[List[Dict[str, str]]] = None,
    prompt_documents: Optional[List[Dict[str, str]]] = None,
) -> str:
    """Build the base system prompt with runtime paths and optional session docs."""
    task_line = f"Task ID: {task_id}" if task_id else "Task ID: (not set)"
    skills_section = _build_skill_lines(skill_summaries)
    prompt_docs_section = _build_prompt_documents_section(prompt_documents)
    logs_line = str(logs_dir) if logs_dir else "(not provided by runner)"
    workspace_skills_line = str(workspace_skills_dir) if workspace_skills_dir else "(not configured)"
    runtime_python_line = str(runtime_python) if runtime_python else "(not provided by runner)"

    return f"""You are an agent running inside agent-alpha.

## Workspace
{task_line}
Workspace root: {workspace_root}

## System Resource Paths
Project skills directory: {skills_dir}
Workspace skills directory: {workspace_skills_line}
Runtime Python: {runtime_python_line}
MCP servers directory: {mcp_servers_dir}
MCP registry: {mcp_registry_path}

## Runtime Records
Logs directory: {logs_line}

## Workspace Rules
- AGENTS.md and SOUL.md are only loaded from the workspace root.
- Do not scan nested folders for AGENTS.md or SOUL.md.
- This workspace is the agent instance's dedicated workspace. It may contain persona docs, private reference materials, and active work files.
- The user may reference other folders by explicit paths in the conversation.
- When the user asks to install a skill without naming a target, install it to the project skills directory.
- When the user asks to install a skill for the current workspace or this agent instance, install it to the workspace skills directory.
- When the user gives a skill repository or URL, inspect the source first, read README/INSTALL-style local docs surfaced by inspection, then present the install and dependency plan before installing.
- Do not infer or run dependency installation commands without explicit user confirmation.
- For Python package installs needed by agent-alpha, prefer `uv pip install --python <Runtime Python> ...` over bare `pip install` so the package lands in the same environment the agent runs.
- Runtime env profile: when the user provides a token, API key, cookie, auth header, or similar credential while installing, configuring, testing, or enabling a skill, CLI, MCP server, or external service, treat it as configuration for future use unless the user explicitly says it is temporary. Save it only to `config/runtime_env.local.json` under the agent-alpha project, using an `env` object, and never write secrets to logs, summaries, command previews, shell profiles, system environment variables, or user-global config.
- If the user explicitly says a credential is temporary or one-time only, use it only for that command/session and do not save it to the runtime env profile.
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
