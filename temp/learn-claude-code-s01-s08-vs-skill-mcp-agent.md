# `learn-claude-code` `s01-s08` 与 `skill-mcp-agent` 函数级横向对比

## 1. 文档范围

本文只比较下面两部分：

- `learning proj/learn-claude-code/agents/s01_agent_loop.py` 到 `s08_background_tasks.py`
- `learning proj/skill-mcp-agent/agent/` 下与之对应的核心实现

关注重点是“函数怎么实现”，不是只讲概念。

---

## 2. 总览结论

先给一句总判断：

`skill-mcp-agent` 已经把 `s01`、`s02`、`s05`、`s06` 这几类能力做成了更工程化的版本；  
但 `s03`、`s04`、`s07`、`s08` 这四类能力，要么没有内建，要么只有很弱的“影子能力”，还没有形成教程里那种清晰、独立、可复用的机制层。

### 对照总表

| 教程章节 | 教程核心机制 | `skill-mcp-agent` 状态 | 判断 |
| --- | --- | --- | --- |
| `s01` | 最小 agent loop | `Agent.run()` + `_call_llm*()` + `_handle_tool_calls()` | 已有，且更工程化 |
| `s02` | 工具定义 + dispatch map | `ToolLoader` + `BaseTool` + 各 Tool 类 + `execute_tool()` | 已有，且更复杂 |
| `s03` | TodoWrite 任务跟踪 | 核心内无 `todo` 状态机、无 nag 提醒 | 缺失 |
| `s04` | Subagent 隔离上下文 | 只有 `task_id` 字段，没有真正子 agent 调度 | 缺失 |
| `s05` | 两层 skill 注入 | 有 skill 自动扫描与注入，但实现方式不同 | 部分对应 |
| `s06` | 上下文压缩 | `ContextManager` 结构化压缩 | 已有，且更强 |
| `s07` | 持久化 task system | 有 session/log/temp 概念，但没有任务板与依赖图 | 缺失 |
| `s08` | 后台任务 + 通知回注 | 有线程，但只用于 ESC 监听和 MCP 事件循环，不是后台任务系统 | 缺失 |

---

## 3. `s01` The Agent Loop vs `skill-mcp-agent` 主循环

### 3.1 教程里的实现

`s01` 的目标是把最小 agent loop 讲清楚。

关键函数：

- `run_bash()`  
  位置：`learning proj/learn-claude-code/agents/s01_agent_loop.py:54`
- `agent_loop(messages)`  
  位置：`learning proj/learn-claude-code/agents/s01_agent_loop.py:68`

实现特征：

1. `agent_loop()` 内部死循环调用 `client.messages.create(...)`
2. 如果 `response.stop_reason != "tool_use"`，直接结束
3. 如果有 `tool_use`，就逐个执行工具
4. 把 `tool_result` 追加回 `messages`
5. 再让模型继续下一轮

这是最纯粹的：

`LLM -> tool_use -> 执行工具 -> tool_result -> 再次 LLM`

### 3.2 `skill-mcp-agent` 里的对应实现

关键函数：

- `Agent.run()`  
  位置：`learning proj/skill-mcp-agent/agent/core/main.py:181`
- `Agent._call_llm()`  
  位置：`learning proj/skill-mcp-agent/agent/core/main.py:236`
- `Agent._call_llm_interruptible()`  
  位置：`learning proj/skill-mcp-agent/agent/core/main.py:303`
- `Agent._handle_tool_calls()`  
  位置：`learning proj/skill-mcp-agent/agent/core/main.py:326`
- `Agent._execute_single_tool()`  
  位置：`learning proj/skill-mcp-agent/agent/core/main.py:406`
- `Agent._build_messages()`  
  位置：`learning proj/skill-mcp-agent/agent/core/main.py:439`
- `LLMClient.generate_with_tools()`  
  位置：`learning proj/skill-mcp-agent/agent/core/llm.py:34`

运行流程：

1. `run()` 先判断是否需要压缩上下文
2. 把用户输入加入 `self.history`
3. 启动 ESC 中断监听
4. 每轮构造 `messages = [system] + history`
5. 通过 `_call_llm_interruptible()` 调 OpenAI tool calling
6. 如果 `message.tool_calls` 不为空，进入 `_handle_tool_calls()`
7. `_handle_tool_calls()` 再逐个执行 `_execute_single_tool()`
8. 工具结果以 `role="tool"` 形式回写到 `history`
9. 再回到下一轮 LLM

### 3.3 具体相同点

- 本质循环完全一样，都是“LLM 决定是否继续调工具”
- 都是把工具结果写回历史，再交给模型继续推理
- 都把“停止条件”交给模型，而不是硬编码流程图

### 3.4 具体不同点

#### 1. 协议层不同

`s01` 用 Anthropic 的 `stop_reason == "tool_use"`。  
`skill-mcp-agent` 用 OpenAI 风格 `message.tool_calls`。

这意味着：

- `s01` 判断循环结束看 `stop_reason`
- `skill-mcp-agent` 判断看 `message.tool_calls`

#### 2. `skill-mcp-agent` 把主循环拆成了多个函数

`s01` 基本全部写在 `agent_loop()` 里。  
`skill-mcp-agent` 已经拆成：

- 调 LLM：`_call_llm()` / `_call_llm_interruptible()`
- 处理工具：`_handle_tool_calls()`
- 单工具执行：`_execute_single_tool()`
- 拼消息：`_build_messages()`

这是明显更接近可维护工程代码的做法。

#### 3. `skill-mcp-agent` 在主循环前后增加了工程能力

教程里没有这些：

- 会话目录初始化：`session_id`、`temp_dir`、`logs_dir`
- 中断控制：`_start_esc_listener()`
- 上下文压缩前置判断：`context_manager.should_compress()`
- 会话日志：`save_session_log()`

#### 4. 历史结构更完整

`s01` 的历史主要是：

- `user`
- `assistant`
- `tool_result`

`skill-mcp-agent` 的历史还会显式保存：

- 带 `tool_calls` 的 `assistant` 消息
- `role="tool"` 的工具结果

这为后面的压缩、调试、日志保存提供了更稳定的原材料。

### 3.5 判断

`s01` 在 `skill-mcp-agent` 里不是缺失，而是已经被“放大成工程版”了。

### 3.6 对重构的启发

这一部分不用大改方向，真正该做的是“减耦合”：

- 保留 `run -> llm -> tool -> history` 这个基本循环
- 继续把会话控制、日志、压缩、中断从 `Agent` 主类里往外拆

---

## 4. `s02` Tool Use vs `skill-mcp-agent` 工具系统

### 4.1 教程里的实现

关键函数：

- `safe_path()`  
  位置：`learning proj/learn-claude-code/agents/s02_tool_use.py:41`
- `run_bash()`  
  位置：`.../s02_tool_use.py:48`
- `run_read()`  
  位置：`.../s02_tool_use.py:61`
- `run_write()`  
  位置：`.../s02_tool_use.py:72`
- `run_edit()`  
  位置：`.../s02_tool_use.py:82`
- `TOOL_HANDLERS`  
  位置：`.../s02_tool_use.py:94`
- `agent_loop()`  
  位置：`.../s02_tool_use.py:114`

它的关键思想只有一句：

“循环没变，只是多了 `TOOLS` 描述和 `{tool_name: handler}` 分发表。”

### 4.2 `skill-mcp-agent` 里的对应实现

核心调度层：

- `ToolLoader.load_all()`  
  位置：`learning proj/skill-mcp-agent/agent/core/tool_loader.py:50`
- `ToolLoader._load_builtin_tools()`  
  位置：`.../tool_loader.py:356`
- `ToolLoader.execute_tool()`  
  位置：`.../tool_loader.py:373`

抽象基类：

- `BaseTool.name`  
  位置：`learning proj/skill-mcp-agent/agent/tools/base_tool.py:16`
- `BaseTool.get_tool_definition()`  
  位置：`.../base_tool.py:23`
- `BaseTool.execute()`  
  位置：`.../base_tool.py:28`

代表性工具类：

- `BashTool.get_tool_definition()` / `execute()`  
  位置：`learning proj/skill-mcp-agent/agent/tools/bash_tool.py:82`, `:107`
- `ReadTool.get_tool_definition()` / `execute()`  
  位置：`learning proj/skill-mcp-agent/agent/tools/read_tool.py`
- `WriteTool.get_tool_definition()` / `execute()`  
  位置：`learning proj/skill-mcp-agent/agent/tools/write_tool.py`
- `EditTool.get_tool_definition()` / `execute()`  
  位置：`learning proj/skill-mcp-agent/agent/tools/edit_tool.py`
- 另外还有 `AppendTool`、`GlobTool`、`GrepTool`、`FetchTool`

### 4.3 具体相同点

- 都要同时维护“工具描述”和“工具实现”
- 都需要一个从“模型返回的工具名”到“本地函数/方法”的路由过程
- 都把读写文件、编辑代码、执行命令当成第一层基础工具

### 4.4 具体不同点

#### 1. 教程版是字典 dispatch；`skill-mcp-agent` 是类注册表

教程：

- `TOOL_HANDLERS = {"bash": ..., "read_file": ...}`

`skill-mcp-agent`：

- 每个工具是一个类
- 统一继承 `BaseTool`
- 由 `ToolLoader._load_builtin_tools()` 动态实例化
- `execute_tool()` 统一调度

这带来的好处是：

- 工具定义和工具执行绑定在一起
- 更容易扩展新工具
- 更容易在工具内部封装平台兼容、返回格式、异常处理

#### 2. `skill-mcp-agent` 的工具类型远比 `s02` 丰富

教程只覆盖：

- `bash`
- `read_file`
- `write_file`
- `edit_file`

`skill-mcp-agent` 除了这些，还有：

- `append`
- `glob`
- `grep`
- `fetch`
- MCP 工具
- Skill 工具

说明它已经从“教学最小工具集”走到了“实际工作工具集”。

#### 3. `skill-mcp-agent` 额外引入了权限系统

教程 `s02` 的风险控制只有 `run_bash()` 里几个危险关键词判断。  
`skill-mcp-agent` 在 `ToolLoader.execute_tool()` 前会先过：

- `PermissionManager.check_permission()`  
  位置：`learning proj/skill-mcp-agent/agent/core/permission_manager.py:49`
- 必要时调用 `ask_user()`  
  位置：`.../permission_manager.py:229`

也就是说，`skill-mcp-agent` 的工具调度链是：

`tool call -> permission -> executor`

而不是教程里的：

`tool call -> executor`

#### 4. `skill-mcp-agent` 对工具返回值做了统一包装和清洗

在 `_handle_tool_calls()` 里会处理：

- dict 转 JSON 字符串
- ANSI 转义清洗
- 工具输出截断
- 特殊 `retry_with_context` 分支

教程 `s02` 基本没有这一层。

### 4.5 判断

`s02` 在 `skill-mcp-agent` 中不但存在，而且已经演化成一套较完整的工具框架。

### 4.6 对重构的启发

这一块不应推倒重来，更适合做的是：

- 把 `ToolLoader` 继续拆成“发现”“注册”“调度”“权限”几个子层
- 让内置工具、MCP 工具、Skill 工具走更统一的注册接口

---

## 5. `s03` TodoWrite vs `skill-mcp-agent`

### 5.1 教程里的实现

关键函数：

- `TodoManager.update()`  
  位置：`learning proj/learn-claude-code/agents/s03_todo_write.py:56`
- `TodoManager.render()`  
  位置：`.../s03_todo_write.py:77`
- `TOOL_HANDLERS["todo"]`  
  位置：`.../s03_todo_write.py:146`
- `agent_loop()` 中 nag reminder  
  位置：`.../s03_todo_write.py:164`

这个机制的关键点不是“有个 todo 列表”，而是：

1. todo 是模型可以主动写入的结构化状态
2. 状态规则是强约束的  
   例如：
   - 最多 20 项
   - `status` 只能是三种
   - 同时只能有一个 `in_progress`
3. agent loop 会监控 todo 是否长期没更新
4. 超过阈值后注入提醒：

```text
<reminder>Update your todos.</reminder>
```

### 5.2 `skill-mcp-agent` 里的对应实现

结论先说：核心里没有真正对应实现。

我做了全局搜索，`skill-mcp-agent` 核心目录里没有：

- `todo` 工具
- `TodoManager`
- 任务清单状态
- nag reminder 机制

最接近但并不等价的只有：

- `Agent.__init__(..., task_id=None)`  
  位置：`learning proj/skill-mcp-agent/agent/core/main.py:45`
- 会话日志、`session_id`、`logs_dir`  
  位置：`.../main.py:65`, `:480`

这些只是“会话标识/日志能力”，不是“可由模型维护的任务状态机”。

### 5.3 具体相同点

几乎没有真正相同点。

最多只能说两者都意识到了“长任务需要额外结构”：

- 教程用 todo 状态
- `skill-mcp-agent` 用日志和 `task_id` 留痕

但这不是一个层级的东西。

### 5.4 具体不同点

#### 1. 教程有结构化任务状态；`skill-mcp-agent` 没有

教程里模型可以主动写：

- `pending`
- `in_progress`
- `completed`

`skill-mcp-agent` 没有任何对应数据结构。

#### 2. 教程有行为约束；`skill-mcp-agent` 没有

`TodoManager.update()` 直接做了状态校验。  
`skill-mcp-agent` 没有类似“任务状态校验器”。

#### 3. 教程有 loop 级督促；`skill-mcp-agent` 没有

`agent_loop()` 会统计 `rounds_since_todo`。  
`skill-mcp-agent` 主循环没有类似：

- “多久没更新计划”
- “多久没汇报进度”
- “任务开着但没收束”

这种元控制逻辑。

### 5.5 判断

`s03` 对应能力在 `skill-mcp-agent` 核心中属于**明确缺失**。

### 5.6 对重构的启发

如果你后面要重构 `agent-alpha`，这一节很值得补：

- 不一定照抄 `TodoWrite`
- 但至少应该有一个“模型可维护的最小任务状态结构”
- 最好还能在 loop 层做轻量提醒

这是提升“复杂任务不跑偏”的低成本机制。

---

## 6. `s04` Subagent vs `skill-mcp-agent`

### 6.1 教程里的实现

关键函数：

- `run_subagent(prompt)`  
  位置：`learning proj/learn-claude-code/agents/s04_subagent.py:116`
- `agent_loop()` 中对 `task` 工具的特殊处理  
  位置：`.../s04_subagent.py:144`

关键实现点：

1. 子 agent 用新的 `sub_messages = [{"role": "user", "content": prompt}]`
2. 子 agent 使用 `SUBAGENT_SYSTEM`
3. 子 agent 的工具集是 `CHILD_TOOLS`
4. 子 agent 没有 `task` 工具，避免递归无限派生
5. 子 agent 只返回最后的摘要文本
6. 子 agent 自己的上下文被丢弃，不污染主上下文

这本质上是“上下文隔离”机制，而不是“多线程”机制。

### 6.2 `skill-mcp-agent` 里的对应实现

结论：核心里没有真正的 subagent 机制。

表面上最接近的是：

- `task_id` 参数  
  位置：`learning proj/skill-mcp-agent/agent/core/main.py:45`
- `_build_system_prompt()` 会把当前 `task_id` 写进 system prompt  
  位置：`.../main.py:134`

但这只是“给当前 agent 打任务标签”，不是：

- 新开一个独立 `messages[]`
- 给子 agent 单独工具集
- 子 agent 返回摘要给父 agent

也就是说，`skill-mcp-agent` 没有 `run_subagent()` 这一层。

### 6.3 具体相同点

- 都意识到“任务隔离”是有价值的
- `skill-mcp-agent` 的 `task_id` 字段说明作者考虑过多任务/多 agent 场景

### 6.4 具体不同点

#### 1. 教程版有真正的上下文隔离；`skill-mcp-agent` 没有

教程的隔离载体是新的 `sub_messages`。  
`skill-mcp-agent` 所有工作都还在同一个 `self.history` 里。

#### 2. 教程版有工具集裁剪；`skill-mcp-agent` 没有

教程会用 `CHILD_TOOLS` 明确禁止子 agent 再继续派发 `task`。  
`skill-mcp-agent` 没有“按 agent 角色裁剪工具集”的机制。

#### 3. 教程版是“摘要回收”；`skill-mcp-agent` 是“同上下文继续写”

教程子 agent 返回的是摘要。  
`skill-mcp-agent` 没有这种“子过程只回收精简信息”的层。

### 6.5 判断

`s04` 对应能力在 `skill-mcp-agent` 核心中也是**明确缺失**。

### 6.6 对重构的启发

如果后面你要做多 agent 或复杂任务拆解，这一节非常关键。

因为它解决的是一个真实问题：

“不是不会做事，而是所有中间探索都堆进一个上下文后，模型会越来越乱。”

---

## 7. `s05` Skill Loading vs `skill-mcp-agent` Skill 机制

### 7.1 教程里的实现

关键函数：

- `SkillLoader._load_all()`  
  位置：`learning proj/learn-claude-code/agents/s05_skill_loading.py:64`
- `SkillLoader._parse_frontmatter()`  
  位置：`.../s05_skill_loading.py:73`
- `SkillLoader.get_descriptions()`  
  位置：`.../s05_skill_loading.py:85`
- `SkillLoader.get_content()`  
  位置：`.../s05_skill_loading.py:99`
- `TOOL_HANDLERS["load_skill"]`  
  位置：`.../s05_skill_loading.py:171`

它是一个标准的“两层注入”：

1. 第一层：system prompt 里只放 skill 简介
2. 第二层：模型真正需要时，调用 `load_skill(name)` 取完整正文

好处是：

- 平时省 token
- 需要时再拉全文
- skill 只是知识，不一定是“可执行工具”

### 7.2 `skill-mcp-agent` 里的对应实现

关键函数：

- `ToolLoader._load_skills()`  
  位置：`learning proj/skill-mcp-agent/agent/core/tool_loader.py:240`
- `ToolLoader._parse_skill()`  
  位置：`.../tool_loader.py:268`
- 内部 `skill_executor(query)`  
  位置：`.../tool_loader.py:332`

### 7.3 具体相同点

- 都扫描技能目录
- 都解析 frontmatter 中的 `name`、`description`
- 都把 skill 内容按需喂给模型，而不是一开始全文塞入上下文

### 7.4 具体不同点

#### 1. 教程版 skill 是“知识加载工具”；`skill-mcp-agent` skill 被包装成“函数工具”

教程：

- 工具名固定叫 `load_skill`
- 参数是 `name`
- 返回 `<skill>...</skill>` 内容

`skill-mcp-agent`：

- 每个 skill 都被单独生成为一个 tool
- 工具名形如 `skill__{name}`
- 调用后直接返回该 skill 的全文

也就是说：

- 教程是“一个总入口 + 技能名参数”
- `skill-mcp-agent` 是“一个 skill 一个 tool”

#### 2. 教程版有“元信息常驻 + 正文按需”；`skill-mcp-agent` 核心里缺了稳定的第一层元信息注入

教程的第一层是：

- `get_descriptions()` 返回简短列表
- 写进 `SYSTEM`

`skill-mcp-agent` 当前更像是：

- 扫描 skill 后直接注册成工具
- 由模型自行看到工具描述并决定调不调

它当然也有“按需加载”的效果，但不是教程里的“两层 skill 注入”同一种设计。

#### 3. 教程里 skill 更偏“说明书”；`skill-mcp-agent` 里 skill 更偏“可调用能力”

这会带来一个设计风格差别：

- 教程更强调知识注入
- `skill-mcp-agent` 更强调把 skill 暴露成工具生态的一部分

### 7.5 判断

`s05` 在 `skill-mcp-agent` 中属于**部分对应**：

- 目标一致：按需引入技能知识
- 结构不同：不是 `load_skill(name)`，而是 `skill__name`

### 7.6 对重构的启发

这一节是未来很适合优化的一块：

- 可以保留 `skill__xxx` 的直接调用能力
- 但最好额外补一个统一的 skill metadata 层
- 让模型先知道“有哪些 skill”，再按需读正文或调用

这样会更接近你想要的“灵活配置 + 降低冗余 token”。

---

## 8. `s06` Context Compact vs `skill-mcp-agent` ContextManager

### 8.1 教程里的实现

关键函数：

- `estimate_tokens(messages)`  
  位置：`learning proj/learn-claude-code/agents/s06_context_compact.py:62`
- `micro_compact(messages)`  
  位置：`.../s06_context_compact.py:68`
- `auto_compact(messages)`  
  位置：`.../s06_context_compact.py:98`

它的思路是三步里的前两步：

1. 粗略估 token
2. 先把旧 `tool_result` 缩成占位符
3. 真超限后保存 transcript 到磁盘
4. 调 LLM 生成连续性摘要
5. 用“摘要 + 确认消息”替换全量历史

### 8.2 `skill-mcp-agent` 里的对应实现

关键函数：

- `ContextManager.__init__()`  
  位置：`learning proj/skill-mcp-agent/agent/core/context_manager.py:24`
- `count_tokens()`  
  位置：`.../context_manager.py:61`
- `count_history_tokens()`  
  位置：`.../context_manager.py:75`
- `should_compress()`  
  位置：`.../context_manager.py:99`
- `compress_history()`  
  位置：`.../context_manager.py:121`
- `_generate_summary()`  
  位置：`.../context_manager.py:198`
- `_json_to_markdown()`  
  位置：`.../context_manager.py:335`

主循环触发点：

- `Agent.run()` 中先判断 `should_compress()`  
  位置：`learning proj/skill-mcp-agent/agent/core/main.py:191`

### 8.3 具体相同点

- 都是“上下文超阈值时做压缩”
- 都会调用 LLM 生成摘要
- 都会保留最近若干轮，压缩更早的历史
- 都希望压缩结果可继续工作，而不是只做归档

### 8.4 具体不同点

#### 1. `skill-mcp-agent` 的 token 预算更精细

教程 `s06`：

- `len(str(messages)) // 4` 粗估

`skill-mcp-agent`：

- 用 `tiktoken`
- 分别计算 `system_tokens`
- `tools_tokens`
- `available_for_history`

这意味着它不是“只看消息长度”，而是按完整上下文预算做控制。

#### 2. `skill-mcp-agent` 的摘要结构远比教程版强

教程摘要只要求：

- 做了什么
- 当前状态
- 关键决策

`skill-mcp-agent` 的 `_generate_summary()` 明确要求 6 个字段：

- `task_timeline`
- `skill_deltas`（注：代码注释里写的是 `skill_deltas`，README 描述更接近 tool delta）
- `important_files`
- `current_state`
- `error_memory`
- `critical_user_intents`

然后 `_json_to_markdown()` 再把结构化 JSON 转成可读 markdown。

这是一个明显更“面向继续执行”的摘要，而不是普通摘要。

#### 3. 教程版有 `micro_compact`；`skill-mcp-agent` 没有这一前置层

教程会先把老 `tool_result` 清成占位符。  
`skill-mcp-agent` 直接在达到阈值时进入整体压缩。

所以两者在压缩策略上是：

- 教程：轻压缩 -> 重压缩
- `skill-mcp-agent`：直接重压缩

#### 4. 教程版会落 transcript；`skill-mcp-agent` 当前主实现更偏内存内压缩

教程 `auto_compact()` 会先把完整历史写入 `transcript_*.jsonl`。  
`skill-mcp-agent` 的 `compress_history()` 主要返回新 `history`，没有把完整 transcript 作为压缩流程的固定产物。

### 8.5 判断

`s06` 在 `skill-mcp-agent` 中是**明确已有且更成熟**的。

### 8.6 对重构的启发

这一块最值得借鉴教程的地方，不是“重写压缩”，而是补两点：

- 增加 `micro_compact` 这一层轻压缩
- 给压缩过程增加 transcript 留档

这样可以让压缩更加温和，也更方便调试和回溯。

---

## 9. `s07` Task System vs `skill-mcp-agent`

### 9.1 教程里的实现

关键函数：

- `TaskManager.create()`  
  位置：`learning proj/learn-claude-code/agents/s07_task_system.py:67`
- `TaskManager.get()`  
  位置：`.../s07_task_system.py:76`
- `TaskManager.update()`  
  位置：`.../s07_task_system.py:79`
- `TaskManager._clear_dependency()`  
  位置：`.../s07_task_system.py:105`
- `TaskManager.list_all()`  
  位置：`.../s07_task_system.py:113`

关键机制：

1. 任务落在 `.tasks/task_x.json`
2. 每个任务持久化在对话外部
3. 支持 `blockedBy` / `blocks`
4. 任务完成时自动清理下游依赖
5. LLM 通过 task tools 管理任务板

它的重点是：

“状态要从聊天历史里搬出去，才能跨压缩、跨轮次稳定存在。”

### 9.2 `skill-mcp-agent` 里的对应实现

核心里没有真正对应的 `TaskManager`。

最相近的是：

- `task_id`  
  位置：`learning proj/skill-mcp-agent/agent/core/main.py:45`
- `session_id`
- `temp_dir`
- `logs_dir`
- `save_session_log()`  
  位置：`.../main.py:480`

但这些都不是任务系统，只是：

- 会话标识
- 临时产物目录
- 日志归档

没有：

- 任务 CRUD
- 任务依赖图
- `.tasks/` 持久化任务板
- 任务完成后自动解锁其他任务

### 9.3 具体相同点

如果勉强说，只能说两者都在尝试把部分状态从纯对话中拿出来：

- 教程拿出去的是任务状态
- `skill-mcp-agent` 拿出去的是日志和临时文件

但这不是同一能力。

### 9.4 具体不同点

#### 1. 教程有“任务对象”；`skill-mcp-agent` 没有

教程任务至少有：

- `id`
- `subject`
- `description`
- `status`
- `blockedBy`
- `blocks`
- `owner`

`skill-mcp-agent` 没有对应对象。

#### 2. 教程的任务系统是可操作的；`skill-mcp-agent` 的 `task_id` 只是标签

`task_id` 目前只会：

- 保存到实例字段
- 写到 system prompt
- 出现在日志元数据里

它不能：

- 创建新任务
- 更新任务状态
- 管理任务依赖

#### 3. 教程任务系统和压缩是互补关系；`skill-mcp-agent` 还没有把这两者打通

教程明确是为了解决：

“对话被压缩之后，任务不能丢。”

`skill-mcp-agent` 目前压缩的是对话，持久化的是日志，但没有任务板层作为稳定支撑。

### 9.5 判断

`s07` 对应能力在 `skill-mcp-agent` 核心中属于**明确缺失**。

### 9.6 对重构的启发

如果未来 `agent-alpha` 要做真正复杂任务，这一节价值很高。

因为：

- `TodoWrite` 适合单次会话内跟踪
- `Task System` 适合跨压缩、跨阶段、跨 agent 的长期目标管理

两者不是替代关系，而是递进关系。

---

## 10. `s08` Background Tasks vs `skill-mcp-agent`

### 10.1 教程里的实现

关键函数：

- `BackgroundManager.run()`  
  位置：`learning proj/learn-claude-code/agents/s08_background_tasks.py:56`
- `BackgroundManager._execute()`  
  位置：`.../s08_background_tasks.py:66`
- `BackgroundManager.check()`  
  位置：`.../s08_background_tasks.py:91`
- `BackgroundManager.drain_notifications()`  
  位置：`.../s08_background_tasks.py:103`
- `agent_loop()` 中的通知注入  
  位置：`.../s08_background_tasks.py:188`

机制要点：

1. `background_run(command)` 立即返回 `task_id`
2. 真正的命令在线程中跑
3. 完成后把结果推入通知队列
4. 每次 LLM 调用前先 `drain_notifications()`
5. 把后台结果作为 `<background-results>` 注入上下文

这解决的是：

“长命令不要阻塞 agent 思考。”

### 10.2 `skill-mcp-agent` 里的对应实现

核心里没有真正对应的后台任务系统。

虽然项目里确实用了线程，但用途不是这个：

- `Agent._start_esc_listener()` 用线程监听中断  
  位置：`learning proj/skill-mcp-agent/agent/core/main.py:278`
- `_call_llm_interruptible()` 用线程包装阻塞式 LLM 调用  
  位置：`.../main.py:303`
- `MCPManager` 用线程跑独立事件循环  
  位置：`learning proj/skill-mcp-agent/agent/tools/mcp_manager.py:39`

这些线程都是“为了控制阻塞或维护连接”，不是：

- 后台任务队列
- 后台任务状态查询
- 后台结果回注模型

### 10.3 具体相同点

- 都使用线程
- 都有“主线程 + 辅助线程”分工

但只是技术手段相同，产品能力不同。

### 10.4 具体不同点

#### 1. 教程线程服务于“异步工作流”；`skill-mcp-agent` 线程服务于“阻塞控制”

教程线程的结果要回流到模型。  
`skill-mcp-agent` 线程主要用于：

- 不中断 UI
- 维持 MCP 连接
- 监听 ESC

#### 2. 教程有任务状态表；`skill-mcp-agent` 没有

教程有：

- `self.tasks`
- `check(task_id)`
- `drain_notifications()`

`skill-mcp-agent` 没有后台任务 registry。

#### 3. 教程会把异步结果重新注入上下文；`skill-mcp-agent` 没有

这是最关键的差别。  
`skill-mcp-agent` 的线程结果不会在下一轮自动变成模型上下文的一部分。

### 10.5 判断

`s08` 对应能力在 `skill-mcp-agent` 核心中属于**明确缺失**。

### 10.6 对重构的启发

如果将来你希望 agent 做：

- 长时间搜索
- 爬取多个来源
- 跑耗时脚本
- 同时做别的分析

那 `s08` 是一个很值得单独引入的机制。

---

## 11. 最终结论：哪些已经有，哪些最值得补

### 已经有而且相对成熟

- `s01` 主循环
- `s02` 工具系统
- `s05` skill 按需加载能力
- `s06` 上下文压缩

### 明显缺失

- `s03` TodoWrite
- `s04` Subagent
- `s07` Task System
- `s08` Background Tasks

### 如果只按重构优先级看，我建议的顺序

1. 先补 `s03`  
   原因：最轻、最容易落地、马上提升复杂任务稳定性

2. 再补 `s07`  
   原因：把“任务状态”从对话里抽离出来，才真正能跨压缩长期工作

3. 再考虑 `s04`
   原因：任务有结构后，子 agent 才有东西可接

4. 最后再考虑 `s08`
   原因：它很有价值，但对你当前项目不是第一堵墙

---

## 12. 一句话总结

`skill-mcp-agent` 现在强在“工具接入、MCP 接入、技能接入、上下文压缩”；  
`learn-claude-code` 的 `s01-s08` 则提醒我们，`skill-mcp-agent` 还缺一层“任务编排与执行控制机制”。

换句话说：

现在的 `skill-mcp-agent` 更像“手很多”；  
但从 `s03/s04/s07/s08` 这四节看，它还不够“会规划、会拆分、会并行、会长期管理任务”。
