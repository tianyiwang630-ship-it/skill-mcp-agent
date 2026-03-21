# `agent-alpha`、`pi-mono`、`learn-claude-code` 总体对比

## 1. 文档范围

这份文档把三个项目放在一起比较：

- 当前项目：`agent-alpha/agent/`
- 学习项目：`learning proj/pi-mono/packages/agent/` + `learning proj/pi-mono/packages/coding-agent/`
- 学习项目：`learning proj/learn-claude-code/agents/s01-s08`

这次的粒度比前两份略高一层：

- 重点看架构层级、模块边界、设计哲学
- 但每个判断都尽量穿插关键类和函数，不只停留在概念层

---

## 2. 先给一句总判断

如果用最直白的话说，这三个项目分别站在三种不同位置上：

- `learn-claude-code`：像“教学拆解版”，核心目标是把 agent harness 的机制一节一节讲清楚
- `pi-mono`：像“平台运行时版”，核心目标是把 agent 运行时做成可扩展框架
- `agent-alpha`：像“业务底座版”，核心目标是把 MCP、skill、内置工具、权限和上下文管理尽快整合成一个可工作的 agent

所以它们不是同一种项目的三份实现，而是三种不同取向：

- `learn-claude-code` 重“原理可见”
- `pi-mono` 重“边界清楚”
- `agent-alpha` 重“能力集成”

---

## 3. 总览对照表

| 维度 | `agent-alpha` | `pi-mono` | `learn-claude-code` | 总结 |
| --- | --- | --- | --- | --- |
| 项目定位 | 可运行的集成式 agent | 可扩展 agent runtime 平台 | Claude Code 机制教学拆解 | 三者目标不同 |
| 主循环 | `Agent.run()` 直编排 | `Agent.prompt()` + `agentLoop()` + `AgentSession` | 每节一个 `agent_loop(messages)` | 教程最纯，pi 最分层，你的最集中 |
| 工具系统 | `ToolLoader` 统一装载/路由 | `createAllTools()` + `_buildRuntime()` | `TOOL_HANDLERS` 显式 dispatch map | 你的最集成，pi 最模块，教程最透明 |
| 工具实现 | 类式 `BaseTool` | 函数工厂 `createReadTool()` | 普通函数 `run_read()` 等 | 抽象层逐步升高 |
| skill | skill 变工具 | skill 变资源索引 | `SkillLoader` + `load_skill` | 三者理念差异很大 |
| 会话管理 | 内存 `history` + JSON log | `SessionManager` JSONL 树 | 单脚本内消息数组 | pi 最强，教程最轻 |
| 压缩 | `ContextManager.compress_history()` | `AgentSession.compact()` + session entry | `micro_compact()` / `auto_compact()` | 你的和 pi 都比教程成熟 |
| 任务机制 | 暂无真正任务板 | 核心默认不带 task/subagent | s03/s04/s07/s08 逐步讲出来 | 教程最系统，但偏教学 |
| 中断/交互 | 双 ESC + 线程 | `abort/steer/followUp` 队列 | 通常无复杂交互层 | pi 交互能力最成熟 |
| 权限治理 | `PermissionManager` 内建 | 无完全对等的统一权限中心 | README 明说故意省略 | 你的项目这块最明确 |
| 扩展面 | MCP + skill + 内置工具 | extension + package + prompt + theme | 机制教学，不是平台扩展 | pi 的扩展面最宽 |

---

## 4. 三者最本质的区别，不在功能，而在“工程目标”

### 4.1 `learn-claude-code`

从 README 就能看出来，这个项目最核心的表达是：

- “The Model IS the Agent”
- “building the harness”
- “每一节只加一个机制”

对应位置：

- `learning proj/learn-claude-code/README.md:42`
- `learning proj/learn-claude-code/README.md:95`
- `learning proj/learn-claude-code/README.md:161`

它的代码风格也完全服务这个目标：

- `s01_agent_loop.py`：只有 `run_bash()` + `agent_loop()`
- `s02_tool_use.py`：加 `run_read()`、`run_write()`、`run_edit()`
- `s03-s08`：每节只新增一个机制类或函数，比如：
  - `TodoManager`
  - `run_subagent()`
  - `SkillLoader`
  - `micro_compact()` / `auto_compact()`
  - `TaskManager`
  - `BackgroundManager`

它不是要做“最适合生产的框架”，而是要让你清楚看到“每个机制是怎么加上去的”。

### 4.2 `pi-mono`

`pi-mono` 的 README 一开始就表明立场：

- minimal terminal coding harness
- adapt pi to your workflows
- 核心默认不带 sub agents 和 plan mode

对应位置：

- `learning proj/pi-mono/packages/coding-agent/README.md:17`
- `learning proj/pi-mono/packages/coding-agent/README.md:19`

它不是教学拆解，也不是业务集成，而是在做一套“平台式运行时”。

### 4.3 `agent-alpha`

你的项目则明显是从 `skill-mcp-agent` 复制而来并继续演化的：

- `Agent` 把主循环、上下文、路径、会话目录整在一起
- `ToolLoader` 把 MCP、skill、内置工具、权限路由整在一起
- `ContextManager` 把 token 预算和压缩整在一起

对应关键类：

- `agent-alpha/agent/core/main.py:42`
- `agent-alpha/agent/core/tool_loader.py:14`
- `agent-alpha/agent/core/context_manager.py:21`

所以你的项目不是“平台优先”，而是“先把能力做全并跑起来”。

---

## 5. 主循环层：三者都围绕同一个 loop，但拆法完全不同

### 5.1 `learn-claude-code`：把 loop 当教学主角

最典型的是：

- `s01_agent_loop.py:68` `agent_loop(messages)`
- `s02_tool_use.py:114` `agent_loop(messages)`
- `s03-s08` 也都保留 `agent_loop(messages)`

它的核心思想非常克制：

1. 调模型
2. 看 stop reason / tool use
3. 执行工具
4. 把结果 append 回 messages
5. 再调模型

它刻意不把循环藏起来。

### 5.2 `agent-alpha`：把 loop 放进总控类

对应实现：

- `agent-alpha/agent/core/main.py:181` `Agent.run()`
- `agent-alpha/agent/core/main.py:236` `_call_llm()`
- `agent-alpha/agent/core/main.py:303` `_call_llm_interruptible()`
- `agent-alpha/agent/core/main.py:326` `_handle_tool_calls()`
- `agent-alpha/agent/core/main.py:406` `_execute_single_tool()`

这里的 loop 已经是工程化版本：

- 有中断
- 有上下文压缩
- 有工具结果截断
- 有调试输出
- 有权限打断后重试

但代价是：主循环细节被包在 `Agent` 里面，`Agent` 会越来越重。

### 5.3 `pi-mono`：把 loop 变成独立引擎

对应实现：

- `learning proj/pi-mono/packages/agent/src/agent.ts:102` `class Agent`
- `learning proj/pi-mono/packages/agent/src/agent.ts:344` `prompt(...)`
- `learning proj/pi-mono/packages/agent/src/agent-loop.ts:28` `agentLoop(...)`
- `learning proj/pi-mono/packages/agent/src/agent-loop.ts:104` `runLoop(...)`
- `learning proj/pi-mono/packages/agent/src/agent-loop.ts:204` `streamAssistantResponse(...)`
- `learning proj/pi-mono/packages/agent/src/agent-loop.ts:300` `executeToolCalls(...)`

这里最值得注意的是：

- `Agent` 不手写完整 tool loop
- loop 被抽成独立模块
- 上层 `AgentSession` 再在这个 loop 外面叠加 session、compaction、extensions、UI 交互

### 5.4 总结

这三者其实形成一条很清楚的梯度：

- `learn-claude-code`：loop 是学习对象
- `agent-alpha`：loop 是工程主控的一部分
- `pi-mono`：loop 是可复用引擎

---

## 6. 工具系统：三者对应的是三个抽象层级

### 6.1 教程：工具就是普通函数 + map

例如：

- `s02_tool_use.py:48` `run_bash()`
- `s02_tool_use.py:61` `run_read()`
- `s02_tool_use.py:72` `run_write()`
- `s02_tool_use.py:82` `run_edit()`

这套写法最好懂：

- 工具定义看得到
- 执行函数看得到
- dispatch map 也看得到

### 6.2 你的项目：工具就是类，加载器统一管理

对应：

- `agent-alpha/agent/tools/base_tool.py:13` `BaseTool`
- `agent-alpha/agent/tools/read_tool.py:11` `ReadTool`
- `agent-alpha/agent/core/tool_loader.py:50` `load_all()`
- `agent-alpha/agent/core/tool_loader.py:373` `execute_tool()`

优点是统一：

- 每个工具都遵守 `name/get_tool_definition/execute`
- `ToolLoader` 可以统一调用

但副作用也明显：

- 工具创建、工具发现、工具权限、工具路由都在一个类附近打转

### 6.3 `pi-mono`：工具是工厂函数，运行时再决定启用哪些

对应：

- `learning proj/pi-mono/packages/coding-agent/src/core/tools/index.ts:129` `createAllTools()`
- `learning proj/pi-mono/packages/coding-agent/src/core/tools/read.ts:49` `createReadTool()`
- `learning proj/pi-mono/packages/coding-agent/src/core/tools/write.ts:35` `createWriteTool()`
- `learning proj/pi-mono/packages/coding-agent/src/core/agent-session.ts:2174` `_buildRuntime()`

这里的哲学是：

- 工具实现尽量轻
- 工具创建是纯构造
- 工具启用策略交给 runtime

### 6.4 总结

三者的工具系统抽象层级可以这样理解：

- `learn-claude-code`：函数级
- `agent-alpha`：类级
- `pi-mono`：工厂 + runtime 级

---

## 7. skill 机制：这是三者差异最大的部分之一

### 7.1 `learn-claude-code`

在教程里，skill 是“两层注入”：

- `s05_skill_loading.py:58` `class SkillLoader`
- `s05_skill_loading.py:188` `agent_loop(messages)`

它的思路是：

1. 先让模型知道有哪些 skill
2. 真需要时，再加载具体 skill 内容
3. 通过 `tool_result` 或上下文注入正文

重点是“按需加载知识”。

### 7.2 `agent-alpha`

在你的项目里：

- `agent-alpha/agent/core/tool_loader.py:240` `_load_skills()`
- `agent-alpha/agent/core/tool_loader.py:268` `_parse_skill()`

skill 直接被变成：

- `skill__xxx` 的工具定义
- 一个返回 skill 全文的执行器

这非常省事，但也意味着：

- skill 和 tool 的边界被抹平了

### 7.3 `pi-mono`

在 `pi-mono` 里：

- `learning proj/pi-mono/packages/coding-agent/src/core/skills.ts:146` `loadSkillsFromDir()`
- `learning proj/pi-mono/packages/coding-agent/src/core/skills.ts:290` `formatSkillsForPrompt()`
- `learning proj/pi-mono/packages/coding-agent/src/core/system-prompt.ts:39` `buildSystemPrompt()`

它把 skill 明确当成资源：

- 扫描 skill 文件
- 校验 frontmatter
- 在 prompt 里只放元信息
- 提示模型用 `read` 去读 skill 文件

### 7.4 总结

如果只看 skill：

- `learn-claude-code` 强调“按需注入”
- `agent-alpha` 强调“直接可调用”
- `pi-mono` 强调“资源索引化”

---

## 8. 会话与上下文：教程最轻，你的项目中等，pi 最重

### 8.1 `learn-claude-code`

前八节基本都以：

- 一个 `messages` 列表
- 脚本内状态类（如 `TodoManager`、`TaskManager`）

来维持上下文。

这是为了教学透明度，不是为了长期会话。

### 8.2 `agent-alpha`

你的核心是：

- `agent-alpha/agent/core/main.py:85` `self.history`
- `agent-alpha/agent/core/main.py:480` `save_session_log()`

也就是：

- 运行时上下文主要在内存里
- 会话结束后再落 JSON 日志

这比教程强很多，但 still 是“消息数组为真相”。

### 8.3 `pi-mono`

`pi-mono` 这一块是最成熟的：

- `learning proj/pi-mono/packages/coding-agent/src/core/session-manager.ts:307` `buildSessionContext()`
- `learning proj/pi-mono/packages/coding-agent/src/core/session-manager.ts:824` `appendMessage()`
- `learning proj/pi-mono/packages/coding-agent/src/core/session-manager.ts:1036` `buildSessionContext()` 实例方法

它的核心不是 `messages[]`，而是：

- append-only session entries
- 每条 entry 有 `id` 和 `parentId`
- `leafId` 决定当前分支
- 最后再从 session tree 投影出 LLM context

### 8.4 总结

这三者在“会话真相”上的层级是：

- `learn-claude-code`：脚本内消息数组
- `agent-alpha`：消息数组 + 附加日志
- `pi-mono`：持久化树结构 + 上下文投影

---

## 9. 上下文压缩：教程讲清思路，你和 pi 在做工程化

### 9.1 `learn-claude-code`

对应：

- `s06_context_compact.py:62` `estimate_tokens()`
- `s06_context_compact.py:68` `micro_compact()`
- `s06_context_compact.py:98` `auto_compact()`

这里的价值在于“压缩机制长什么样”讲得很清楚。

### 9.2 `agent-alpha`

对应：

- `agent-alpha/agent/core/context_manager.py:99` `should_compress()`
- `agent-alpha/agent/core/context_manager.py:121` `compress_history()`
- `agent-alpha/agent/core/context_manager.py:198` `_generate_summary()`

你的实现已经很像正式能力了：

- 有 token 预算
- 有 structured summary
- 有摘要 markdown 化
- 有失败回退

### 9.3 `pi-mono`

对应：

- `learning proj/pi-mono/packages/coding-agent/src/core/agent-session.ts:1547` `compact()`
- `learning proj/pi-mono/packages/coding-agent/src/core/agent-session.ts:1683` `_checkCompaction()`
- `learning proj/pi-mono/packages/coding-agent/src/core/agent-session.ts:1765` `_runAutoCompaction()`
- `learning proj/pi-mono/packages/coding-agent/src/core/session-manager.ts:864` `appendCompaction()`

它更进一步的地方在于：

- compaction 不是改一段内存数组
- 而是成为正式 session entry

### 9.4 总结

压缩这块最适合用一句话概括：

- `learn-claude-code` 教你“为什么要压、怎么压”
- `agent-alpha` 已经把“压缩能力”做成了组件
- `pi-mono` 把“压缩能力”嵌进了完整 session 生命周期

---

## 10. 任务、子代理、后台执行：教程最完整，但你和 pi 都没走同一路

### 10.1 `learn-claude-code`

前八节里，这块是它最成体系的地方：

- `s03_todo_write.py:52` `class TodoManager`
- `s04_subagent.py:116` `run_subagent()`
- `s07_task_system.py:47` `class TaskManager`
- `s08_background_tasks.py:50` `class BackgroundManager`

这四节实际上已经组成一条很完整的演化链：

- 先有计划
- 再有子任务上下文隔离
- 再有磁盘任务系统
- 再有后台执行

### 10.2 `agent-alpha`

你现在的项目里，这一条链基本没有真正落地：

- 有 `task_id`
- 有 session/log/temp
- 但没有真正的 todo/task board/background manager/subagent runtime

这也是你前面已经明确说“先不重构”的部分。

### 10.3 `pi-mono`

`pi-mono` 在 README 里就说得很明白：

- 它默认不带 sub agents 和 plan mode

对应：

- `learning proj/pi-mono/packages/coding-agent/README.md:19`

也就是说，这块不是它不会做，而是它故意不塞进核心。

### 10.4 总结

这里三者形成了一个很有意思的分工：

- `learn-claude-code`：把这些机制讲出来
- `pi-mono`：有意不把它们塞进核心
- `agent-alpha`：当前也没真正建起来

所以如果以后你要补这一块，最值得借的仍然是教程，而不是照搬 `pi-mono`。

---

## 11. prompt 构建：教程最轻，pi 最纯，你的项目最直给

### 11.1 `learn-claude-code`

教程里通常是：

- 常量 `SYSTEM`
- 每节按机制加少量提示

它故意不把 prompt 构建做复杂。

### 11.2 `agent-alpha`

对应：

- `agent-alpha/agent/core/main.py:134` `_build_system_prompt()`

优点是：

- 路径规则和工作空间规则非常直白
- 业务上很快能用

缺点是：

- prompt 和 `Agent` 实例绑定得太紧

### 11.3 `pi-mono`

对应：

- `learning proj/pi-mono/packages/coding-agent/src/core/agent-session.ts:758` `_rebuildSystemPrompt()`
- `learning proj/pi-mono/packages/coding-agent/src/core/system-prompt.ts:39` `buildSystemPrompt()`

这里的好处在于：

- runtime 收集资源
- prompt builder 做纯拼接
- tool、skill、context file 一变，可以重建 prompt

### 11.4 总结

prompt 构建的三种风格：

- 教程：最少够用
- 你的项目：直给、实战优先
- `pi-mono`：函数式拼装、边界最清楚

---

## 12. 权限与治理：你的项目最显式，教程最少，pi 更分散

### 12.1 `learn-claude-code`

README 已经明确说：

- 它故意省略了完整权限治理

对应：

- `learning proj/learn-claude-code/README.md:219`
- `learning proj/learn-claude-code/README.md:226`

### 12.2 `agent-alpha`

对应：

- `agent-alpha/agent/core/permission_manager.py:11` `PermissionManager`
- `agent-alpha/agent/core/permission_manager.py:49` `check_permission()`
- `agent-alpha/agent/core/permission_manager.py:229` `ask_user()`
- `agent-alpha/agent/core/tool_loader.py:373` `execute_tool()`

这是你项目里非常成型的一块：

- deny/allow/ask
- 规则匹配
- 会话级缓存
- 工具执行前统一拦截

### 12.3 `pi-mono`

`pi-mono` 并没有一个和你完全对等的统一权限中心。

它更偏向：

- runtime/tool 自己约束边界
- extension UI 可以 `confirm`
- session / interactive mode 支持 abort、queue、dialog

也就是说，它把“治理”分散到了多个层面。

### 12.4 总结

如果单看“权限治理”这一块：

- 教程：故意简化
- `pi-mono`：分散式
- `agent-alpha`：集中式

这反而是你项目非常有保留价值的一块。

---

## 13. 三者最值得借鉴的地方分别是什么

### 13.1 从 `learn-claude-code` 借什么

最值得借的是“机制拆分方式”，不是代码表面形式：

- `s01-s02`：loop 和 tool handler 的最小骨架
- `s05`：按需知识加载
- `s06`：压缩策略表达
- `s03/s04/s07/s08`：如果以后你要做任务系统，这套最值得学

### 13.2 从 `pi-mono` 借什么

最值得借的是“运行时边界感”：

- 底层 `Agent` 和上层 `AgentSession` 分开
- `agentLoop` 单独成引擎
- `SessionManager` 把存储真相和 LLM context 分开
- `buildSystemPrompt()` 变纯函数
- 工具创建和工具启用策略分开

### 13.3 `agent-alpha` 自己应该保留什么

最应该保留的反而是你已经做得很实用的东西：

- `PermissionManager`
- `ToolLoader` 里的 MCP 自动发现与按需搜索思路
- `ContextManager` 的结构化压缩
- 当前这种路径 prompt 和工作空间约束

---

## 14. 如果把三者放成一条演化链，我会这样理解

可以把它们看成三个不同层次的答案：

### 第一层：`learn-claude-code`

回答的是：

“一个 agent harness 是由哪些机制组成的？”

### 第二层：`agent-alpha`

回答的是：

“怎样把这些机制尽快揉成一个能工作的项目？”

### 第三层：`pi-mono`

回答的是：

“怎样把 agent 运行时做成一个边界清楚、可插拔的系统？”

所以三者不是互相替代，而是：

- 教程给你机制地图
- 你的项目给你集成经验
- `pi-mono` 给你架构边界

---

## 15. 最后一句话总结

如果只让我用一句话总结三者区别，我会这样说：

`learn-claude-code` 教你 agent harness 的骨架，  
`agent-alpha` 证明这些能力可以被快速揉成一个可工作的系统，  
`pi-mono` 则展示了如何把这套系统继续抽象成运行时框架。

所以对你现在最有价值的，不是选边站，而是把三者放在一条线上看：

- 用 `learn-claude-code` 判断“缺没缺机制”
- 用 `agent-alpha` 判断“能力有没有落地”
- 用 `pi-mono` 判断“边界是不是太乱”

