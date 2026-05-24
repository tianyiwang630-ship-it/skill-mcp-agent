# 个人偏好
1 我不懂代码，你和我交流要用我能理解的表达方式
2 执行前，必须和我讨论1-3轮，收束边界才能执行
3 如果需要写后端接口，后端接口使用fastapi库，遵循RESTFUL api的规范。
4 代码风格要简洁，如无必要毋增实体；代码要清晰，注重模块化和可扩展性。
5 中间产物放进temp文件夹，尤其是pytest
6 项目有更改，功能迭代、架构调整、bug修复等要写到开发日志.md里，记录日期、背景和关键更改内容，但是没改项目就不要记
7 阅读中文内容，用utf-8
8 python环境是anaconda的ai12，D:\Anaconda\envs\ai12\python.exe

# 背景知识
learning proj是用来学习和借鉴的项目文件夹。其中，skill-mcp-agent是我之前的项目。
agent-alpha是现在focus的项目，希望能够简化skill-mcp-agent（agent-alpha内容就是skill-mcp-agent复制来的），并借鉴learning proj中的pi-mono、nanobot、openclaw、learn-claude-code、claw-code、hermes agent以及playwright。
agent-beta也是focus的项目，是打算从0开始新建一个，和agent-alpha这条“从skill-mcp-agent出发逐步简化”的路线不同。
期望改的目标：1 减少冗余代码 2 优化代码架构 3 提高配置灵活性和模块化，包括但是不限于记忆模块、压缩模块、自我模块和情感模块 4 提升鲁棒性 5 每一个agent类，可以输入工作路径、自动识别agent人格md文档，便于多agent编排
 
# 当下进展
要完善agent实例化，并且要能达到安装learning proj里的agent reach这样的cli工具skill，以及良好的subagent/cron功能，且可以为日后多agent编排打下基础

# 遵守的规范

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.