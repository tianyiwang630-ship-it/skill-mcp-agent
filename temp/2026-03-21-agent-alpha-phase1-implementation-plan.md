# Agent Alpha Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thin the core runtime without changing user-facing behavior, and switch skills to a unified `load_skill(name)` two-layer loading model.

**Architecture:** Keep `Agent` as the assembly/entry shell, move loop execution into a small `AgentLoop`, move skill scanning into `SkillLoader`, and move prompt assembly into a pure builder. `ToolLoader` continues to own tool registration/execution, but no longer creates one tool per skill.

**Tech Stack:** Python, pytest, existing OpenAI client/tooling, markdown/YAML-frontmatter parsing via lightweight local parsing

---

## File Map

- Modify: `agent-alpha/agent/core/main.py`
- Modify: `agent-alpha/agent/core/tool_loader.py`
- Create: `agent-alpha/agent/core/agent_loop.py`
- Create: `agent-alpha/agent/core/skill_loader.py`
- Create: `agent-alpha/agent/core/system_prompt_builder.py`
- Create: `agent-alpha/tests/core/test_skill_loader.py`
- Create: `agent-alpha/tests/core/test_tool_loader_skills.py`

## Chunk 1: Skill Loading

- [ ] Write a failing test for parsing `SKILL.md` frontmatter and body split.
- [ ] Run the focused pytest case and confirm it fails for missing `SkillLoader`.
- [ ] Implement `SkillLoader` with scan, descriptions, and `get_content(name)`.
- [ ] Run the focused pytest case and confirm it passes.

## Chunk 2: Unified `load_skill`

- [ ] Write a failing test proving `ToolLoader` exposes `load_skill` and no `skill__*` tools.
- [ ] Run the focused pytest case and confirm it fails against the old behavior.
- [ ] Update `ToolLoader` to register a single `load_skill` executor backed by `SkillLoader`.
- [ ] Run the focused pytest case and confirm it passes.

## Chunk 3: Prompt Wiring

- [ ] Write a failing test for system prompt skill summary rendering.
- [ ] Run the focused pytest case and confirm it fails for missing prompt builder wiring.
- [ ] Implement `system_prompt_builder.py` and wire `Agent` to use skill summaries in prompt generation.
- [ ] Run the relevant tests and confirm they pass.

## Chunk 4: Loop Extraction

- [ ] Add a focused test or smoke check target for the loop extraction boundary if feasible.
- [ ] Extract the loop logic from `main.py` into `agent_loop.py` with behavior preserved.
- [ ] Re-run the targeted test set and a lightweight import/compile check.

## Chunk 5: Verification

- [ ] Run the new pytest subset.
- [ ] Run a lightweight syntax/import check.
- [ ] Summarize changed files and residual risks.

