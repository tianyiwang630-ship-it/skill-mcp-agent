# `agent-alpha` 第一阶段重构设计

## 1. 目标

第一阶段只做两件事：

1. 把核心骨架变薄、边界变清楚
2. 把 skill 机制改成 `learn-claude-code s05` 那种统一 `load_skill(name)` 的两层加载

这一步不追求：

- 引入任务系统
- 引入子 agent
- 引入后台任务
- 一步做成 `pi-mono` 那种平台化运行时
- 立刻接入“工作路径 + 自动识别人格 md”

第一阶段的定位很明确：

**先整理底层骨架，为第二阶段铺路。**

---

## 2. 范围边界

### 2.1 这次要动的核心文件

- `agent-alpha/agent/core/main.py`
- `agent-alpha/agent/core/tool_loader.py`
- `agent-alpha/agent/core/context_manager.py`

### 2.2 这次允许新增的小模块

建议新增：

- `agent-alpha/agent/core/agent_loop.py`
- `agent-alpha/agent/core/skill_loader.py`
- `agent-alpha/agent/core/system_prompt_builder.py`

### 2.3 这次先不动的方向

- `s03` Todo / plan 跟踪
- `s04` subagent
- `s07` task system
- `s08` background tasks
- agent 人格 md 自动识别

---

## 3. 第一阶段后的目标结构

第一阶段结束后，核心职责收成 5 个角色：

1. `Agent`
2. `AgentLoop`
3. `ToolLoader`
4. `SkillLoader`
5. `SystemPromptBuilder`

它们的关系是：

- `Agent` 负责组装
- `AgentLoop` 负责消息循环
- `ToolLoader` 负责工具注册与分发
- `SkillLoader` 负责 skill 资源管理
- `SystemPromptBuilder` 负责 prompt 拼装

---

## 4. 模块职责设计

## 4.1 `Agent`

文件：

- `agent-alpha/agent/core/main.py`

第一阶段后，`Agent` 只保留这些职责：

- 初始化工作路径、输入输出目录、临时目录、日志目录
- 初始化 `LLMClient`
- 初始化 `ToolLoader`
- 初始化 `SkillLoader`
- 初始化 `ContextManager`
- 生成 system prompt
- 持有 `history`
- 对外暴露 `run(user_input)`

它不再亲自承担整条主循环的内部细节。

也就是说，`Agent` 从现在的“总控大类”，收成“组装器 + 入口壳”。

---

## 4.2 `AgentLoop`

新文件：

- `agent-alpha/agent/core/agent_loop.py`

职责：

- 执行单轮/多轮消息循环
- 调用 LLM
- 判断是否需要继续工具调用
- 执行工具调用
- 把工具结果回写到 `history`
- 处理中断逻辑

从当前 `main.py` 中迁出的逻辑包括：

- `run()` 里的循环主体
- `_call_llm_interruptible()`
- `_handle_tool_calls()`
- `_execute_single_tool()`

第一阶段原则：

- 尽量保持行为不变
- 不重写交互语义
- 只是把循环逻辑从 `Agent` 身上拿下来

---

## 4.3 `ToolLoader`

文件：

- `agent-alpha/agent/core/tool_loader.py`

第一阶段后保留职责：

- 加载 MCP 工具
- 加载内置工具
- 注册统一的 `load_skill` 工具
- 维护工具定义和执行器
- 做权限检查
- 做工具执行分发

第一阶段后移除职责：

- 不再为每个 skill 生成一个 `skill__xxx` 工具
- 不再承担 skill 资源扫描和正文管理

第一阶段后，`ToolLoader` 仍然是“工具中心”，但不再是“技能系统本体”。

---

## 4.4 `SkillLoader`

新文件：

- `agent-alpha/agent/core/skill_loader.py`

职责：

- 扫描 `skills/<name>/SKILL.md`
- 解析 YAML frontmatter
- 提供 skill 摘要列表
- 按 skill 名称返回正文 body

它只负责“skill 资源管理”，不负责工具执行。

### 读取规则

采用 `learn-claude-code s05` 的两层加载思路：

#### Layer 1：启动时只读取轻信息

读取 YAML 头部中的：

- `name`
- `description`

可选保留：

- `tags`

这些信息用于：

- 生成 skill 摘要
- 注入 system prompt

#### Layer 2：按需读取正文

当模型调用：

```text
load_skill(name="pdf")
```

再返回 skill 正文：

```text
<skill name="pdf">
...
</skill>
```

### 注意

这里第一层读取的是：

**YAML frontmatter**

不是全文。

正文只在 `load_skill(name)` 时返回。

---

## 4.5 `SystemPromptBuilder`

新文件：

- `agent-alpha/agent/core/system_prompt_builder.py`

职责：

- 根据工作目录信息生成基础 prompt
- 注入路径规则
- 注入大文件写入规则
- 注入 skill 摘要
- 为未来注入 agent 人格 md / AGENTS.md 留入口

第一阶段目标不是把 prompt 做复杂，而是把它从 `Agent` 类里拿出来，变成一个清楚的拼装函数。

---

## 5. Skill 机制改造方案

## 5.1 当前方案

当前 `agent-alpha` 的 skill 机制是：

- 每个 skill 扫描后变成一个独立工具
- 工具命名类似 `skill__pdf`
- 模型调用 skill 时，本质上是在调用某个专属工具

这个方案已经有“渐进披露”的雏形，但问题是：

- skill 数量越多，工具列表越大
- skill 和 tool 的边界混在一起
- `ToolLoader` 职责变重

## 5.2 第一阶段目标方案

第一阶段统一改为：

- skill 不再逐个变成工具
- 工具列表里只保留一个通用技能工具：`load_skill`
- skill 摘要进入 prompt
- skill 正文按需加载

### 启动时

prompt 中出现：

```text
Skills available:
- pdf: Process PDF files
- code-review: Review code changes
```

### 运行时

工具中只出现一个：

```text
load_skill(name)
```

调用后返回：

```text
<skill name="pdf">
...
</skill>
```

## 5.3 为什么采用这个方案

原因有 5 个：

1. 工具列表不会随着 skill 增加而膨胀
2. skill 的角色更清楚，更像知识资源
3. `ToolLoader` 会明显变轻
4. 更接近 `learn-claude-code s05`
5. 为后续人格 md / 资源 md / agent profile 的统一加载方式铺路

---

## 6. 数据流设计

第一阶段后的主要数据流：

### 6.1 初始化阶段

1. `Agent` 初始化工作空间和目录
2. `SkillLoader` 扫描所有 `SKILL.md`
3. `ToolLoader` 加载：
   - MCP 工具
   - 内置工具
   - 通用 `load_skill`
4. `SystemPromptBuilder` 根据：
   - 工作路径
   - 路径规则
   - skill 摘要
   构建 system prompt
5. `ContextManager` 初始化 token 预算

### 6.2 运行阶段

1. 用户输入进入 `Agent.run()`
2. `Agent` 把消息交给 `AgentLoop`
3. `AgentLoop` 调模型
4. 如果模型调用普通工具：
   - 走 `ToolLoader.execute_tool()`
5. 如果模型调用 `load_skill(name)`：
   - `ToolLoader` 转发给 `SkillLoader.get_content(name)`
6. tool result 写回 `history`
7. 再次进入模型循环

---

## 7. 错误处理策略

第一阶段原则：

**保守，不追求新花样，只保证行为清晰。**

### 7.1 `load_skill` 找不到 skill

返回明确错误字符串：

- 提示 skill 名称不存在
- 同时列出可用 skill 名称

### 7.2 skill frontmatter 不合法

处理方式：

- 启动时跳过该 skill
- 打印 warning

### 7.3 正文为空

允许 skill 存在，但 `load_skill` 返回空正文提示

### 7.4 主循环和中断

第一阶段不改交互语义：

- 继续保留当前中断行为
- 只是把逻辑迁移到 `AgentLoop`

---

## 8. 第一阶段不改的东西

以下内容即使未来需要改，这一阶段也不主动展开：

- 上下文压缩策略本身
- 权限规则本身
- MCP 搜索逻辑本身
- session log 结构
- 多 agent 编排
- 人格 md 自动识别

原因很简单：

第一阶段目标是“骨架清楚”，不是“功能大升级”。

---

## 9. 验证目标

第一阶段完成后，至少要确认这些行为没有回退：

1. 普通内置工具还能调用
2. MCP 工具还能正常加载和调用
3. `load_skill(name)` 能正确返回 skill 正文
4. system prompt 中能看到 skill 摘要
5. 旧的 `skill__xxx` 不再暴露
6. 权限系统仍然能工作
7. 上下文压缩仍然能工作
8. 中断行为与当前版本保持一致

---

## 10. 这一阶段完成后的收益

第一阶段做完后，项目不会一下子变成“大平台”，但会明显更顺：

### 10.1 对当前的收益

- `main.py` 会更薄
- `tool_loader.py` 会更薄
- skill 系统职责更清楚
- 后续阅读成本下降

### 10.2 对第二阶段的收益

以后如果要加：

- 每个 agent 传入工作路径
- 自动识别人格 md
- 不同 agent 读取不同 profile

就可以直接挂在：

- `SystemPromptBuilder`
- `SkillLoader` 类似的资源加载层
- `Agent` 的初始化参数

不需要再次拆主循环和 skill 机制。

---

## 11. 一句话结论

第一阶段的正确目标不是“把 `agent-alpha` 重写成 `pi-mono`”，而是：

**把 `agent-alpha` 从几个很能干的大文件，整理成几个职责清楚的小核心模块；同时把 skill 从“专属工具”收回成“按需加载的知识资源”。**

