# `agent-alpha` 与 `pi-mono` 的函数/类级横向对比

## 1. 文档范围

这份文档比较的是：

- 你的当前项目：`agent-alpha/agent/`
- 学习项目：`learning proj/pi-mono/packages/agent/` 和 `learning proj/pi-mono/packages/coding-agent/`

这里的重点不是只讲“理念”，而是尽量落到“关键类和函数是怎么写的、怎么分工的”这一层。

---

## 2. 一句话先说结论

如果用最直白的话说：

- `agent-alpha` 是“一个大一点的总控类，自己直接把会话、主循环、工具调用、上下文压缩、路径 prompt 都串起来”
- `pi-mono` 是“把底层 agent 循环、上层 session/runtime、资源加载、工具工厂、交互模式拆成了几层”

所以两者不是谁“更先进”这么简单，而是：

- `agent-alpha` 更直接，容易顺着一条链看懂
- `pi-mono` 更分层，扩展点更多，但理解成本也更高

---

## 3. 对照总表

| 对比点 | `agent-alpha` | `pi-mono` | 判断 |
| --- | --- | --- | --- |
| 主入口 | `Agent` 一类承担大部分编排 | `packages/agent` 负责底层循环，`AgentSession` 负责运行时 | `pi-mono` 分层更清楚 |
| 消息循环 | `Agent.run()` 里直接循环 | `Agent.prompt()` 调 `agentLoop()` / `runLoop()` | `pi-mono` 更像“引擎 + 壳” |
| 工具注册 | `ToolLoader.load_all()` 统一装载 | `createAllTools()` + `_buildRuntime()` 组装 | `pi-mono` 更模块化 |
| 工具实现形态 | `BaseTool` 抽象类 + 各工具类 | 工具工厂函数 `createReadTool()` 等 | `pi-mono` 更轻 |
| skill | skill 被转成可调用工具 | skill 默认只进 prompt，需要时再 `read` | 哲学不同 |
| 会话持久化 | `history` 在内存，结束时另存 JSON 日志 | `SessionManager` 以 JSONL 树实时持久化 | `pi-mono` 更强很多 |
| 上下文压缩 | `ContextManager` 直接压缩 `history` | `SessionManager + AgentSession.compact()` 联动 | `pi-mono` 抽象更完整 |
| 中断 | 双 ESC + 线程事件 | `abort/steer/followUp` 队列化 | `pi-mono` 交互能力更成熟 |
| 权限/安全 | `PermissionManager` 明确内建 | 没有一个对等的全局权限中心 | 你的项目这块更直给 |
| 扩展机制 | 主要靠 MCP、skill、内置工具 | extension、resource loader、session hook | `pi-mono` 扩展面更广 |

---

## 4. 主循环：`Agent.run()` vs `Agent.prompt() + agentLoop()`

### 4.1 `agent-alpha` 怎么做

核心入口在 `agent-alpha/agent/core/main.py`：

- `Agent.run()`：`181` 行
- `_call_llm()`：`236` 行
- `_call_llm_interruptible()`：`303` 行
- `_handle_tool_calls()`：`326` 行
- `_execute_single_tool()`：`406` 行
- `_build_messages()`：`439` 行

它的执行链基本是：

1. `run()` 先判断是否压缩上下文
2. 把用户消息 append 到 `self.history`
3. 启动 ESC 监听线程
4. 在 `for turn in range(...)` 里：
   - `_build_messages()`
   - `_call_llm_interruptible()`
   - 如果模型要调工具，就 `_handle_tool_calls()`
   - 如果没有工具调用，就把 assistant 文本写回 `history` 并返回

也就是说，`Agent` 既是：

- 状态容器
- 循环控制器
- 工具执行协调器
- 中断控制器
- prompt 构造器

这是一个很典型的“总控类自己把事做完”的写法。

### 4.2 `pi-mono` 怎么做

`pi-mono` 把这一层拆成了两级：

#### 第一级：底层 Agent 状态与运行入口

在 `learning proj/pi-mono/packages/agent/src/agent.ts`：

- `class Agent`：`102` 行
- `prompt()`：`342` 行
- `_runLoop` 所在逻辑段：`421-560`
- `setTools()`：`244` 行
- `replaceMessages()`：`248` 行
- `appendMessage()`：`252` 行
- `steer()` / `followUp()` / `abort()`：`260`、`268`、`323` 行

这里的 `Agent` 更像“运行引擎壳”：

- 持有 `state`
- 持有队列
- 负责发事件
- 负责把调用委托给 `agentLoop()`

它自己并不直接在类方法里手写“工具调用 while 循环”。

#### 第二级：独立的循环实现

在 `learning proj/pi-mono/packages/agent/src/agent-loop.ts`：

- `agentLoop()`：`28` 行
- `agentLoopContinue()`：`65` 行
- `runLoop()`：`104` 行
- `streamAssistantResponse()`：`204` 行
- `executeToolCalls()`：`300` 行

这里才是真正的循环核心：

1. `runLoop()` 管 turn 级循环
2. `streamAssistantResponse()` 专门管模型响应流
3. `executeToolCalls()` 专门管工具调用及结果回写
4. `getSteeringMessages()` / `getFollowUpMessages()` 把中途插话和后续消息也纳入循环

### 4.3 相同点

- 两边本质上都是“用户消息 -> 调模型 -> 如果有工具就执行 -> 再喂回模型 -> 直到得到最终答复”
- 两边都把工具结果重新写回上下文，而不是只在屏幕显示
- 两边都有“中断当前运行”的概念

### 4.4 关键差异

最大的差异不是功能，而是“循环代码放在哪里”：

- `agent-alpha`：循环逻辑粘在 `Agent` 类里
- `pi-mono`：循环逻辑抽成了独立文件 `agent-loop.ts`

这个差异带来的后果很大：

- `agent-alpha` 读起来路径短，但 `Agent` 很容易越长越胖
- `pi-mono` 单看一个类反而更薄，因为真正复杂度被拆到 loop 引擎里了

我的判断是：

`agent-alpha` 的问题不是“循环写错了”，而是“总控类承载了太多循环细节”；  
`pi-mono` 在这块更像一个可以复用的底层引擎。

---

## 5. LLM 调用边界：`LLMClient` vs `convertToLlm + streamSimple`

### 5.1 `agent-alpha`

在 `agent-alpha/agent/core/llm.py`：

- `LLMClient.generate()`：`14` 行
- `LLMClient.generate_with_tools()`：`34` 行

这一层比较薄，职责很明确：

- 收到 `messages` 和 `tools`
- 直接调用 `OpenAI(...).chat.completions.create(...)`
- 把原始响应对象返回给上层

也就是说，`LLMClient` 几乎只是一个 SDK 包装层。

### 5.2 `pi-mono`

`pi-mono` 把这个边界拆得更细：

- `agent.ts` 中保留 `convertToLlm`、`transformContext`、`onPayload` 这些钩子
- `agent-loop.ts` 的 `streamAssistantResponse()` 里才真正：
  - `transformContext(messages)`
  - `convertToLlm(messages)`
  - 组装 `llmContext`
  - 调 `streamSimple()` 或自定义 `streamFn`

对应位置：

- `agent.ts`：`117-145`
- `agent.ts`：`436-455`
- `agent-loop.ts`：`204-237`

### 5.3 关键差异

`agent-alpha` 的 LLM 层是“一个简单调用器”；  
`pi-mono` 的 LLM 边界是“一个可插拔调用管线”。

这意味着：

- 你的项目更容易快速跑起来
- `pi-mono` 更容易插入“改上下文、换 transport、做 provider hook、注入 payload 预处理”这些能力

---

## 6. 工具注册与执行：`ToolLoader` vs `createAllTools() + _buildRuntime()`

### 6.1 `agent-alpha`

核心在 `agent-alpha/agent/core/tool_loader.py`：

- `ToolLoader.load_all()`：`50` 行
- `_load_mcp_tools()`：`75` 行
- `_load_skills()`：`240` 行
- `_parse_skill()`：`268` 行
- `_load_builtin_tools()`：`356` 行
- `execute_tool()`：`373` 行

这一层的特点是“统一入口”：

1. 先扫 MCP
2. 再扫 skills
3. 再装内置工具
4. 最后统一由 `execute_tool()` 分发

`execute_tool()` 里面又分了几条特殊路由：

- `tool_search`
- `mcp__*`
- `skill__*`
- 普通内置工具

这很实用，但也意味着 `ToolLoader` 不只是“加载器”，它已经半兼任“路由器”和“策略中心”。

### 6.2 `pi-mono`

`pi-mono` 把工具系统拆成两层：

#### 工具工厂层

在 `learning proj/pi-mono/packages/coding-agent/src/core/tools/index.ts`：

- `createCodingTools()`：`110` 行
- `createReadOnlyTools()`：`122` 行
- `createAllTools()`：`129` 行

这里做的只是“按 cwd 生成工具实例”，并不负责会话策略。

#### 运行时组装层

在 `learning proj/pi-mono/packages/coding-agent/src/core/agent-session.ts`：

- `_buildRuntime()`：`2174` 行
- `setActiveToolsByName()`：`663` 行
- `_rebuildSystemPrompt()`：`758` 行

这里才决定：

- 哪些基础工具启用
- 是否注入扩展工具
- 如何重建 tool registry
- 工具变了以后如何同步 system prompt

### 6.3 关键差异

`agent-alpha` 是“工具加载、工具路由、工具权限、部分工具搜索”都压在 `ToolLoader`。  
`pi-mono` 是“工具创建”和“工具启用策略”分开。

这就是为什么你会感觉自己的 `ToolLoader` 很能干，但也很重。

---

## 7. 工具实现形态：类式工具 vs 函数式工具

### 7.1 `agent-alpha`

在 `agent-alpha/agent/tools/base_tool.py`：

- `BaseTool` 用抽象类约束：
  - `name`
  - `get_tool_definition()`
  - `execute(**kwargs)`

在 `agent-alpha/agent/tools/read_tool.py`：

- `ReadTool.get_tool_definition()` 手写 OpenAI function schema
- `ReadTool.execute()` 自己做：
  - 路径处理
  - 编码兜底
  - 行号格式化
  - 长行截断
  - 友好报错

这种方式的好处是：

- 面向对象，直觉上比较好懂
- 每个工具自己带“定义 + 实现”

但代价是：

- schema 和执行逻辑绑得比较紧
- 想做“替换底层文件系统实现”不太自然

### 7.2 `pi-mono`

在 `learning proj/pi-mono/packages/coding-agent/src/core/tools/read.ts`：

- `createReadTool(cwd, options?)`：`49` 行
- `ReadOperations`：`27` 行

在 `write.ts`：

- `createWriteTool(cwd, options?)`：`35` 行
- `WriteOperations`：`18` 行

这里的写法明显更函数式：

- schema 单独定义
- tool 通过工厂函数创建
- 底层 I/O 通过 `operations` 注入

例如 `read.ts` 里，读文件不是写死在工具里，而是抽成：

- `readFile`
- `access`
- `detectImageMimeType`

这让它后面很容易：

- 接远程文件系统
- 接 SSH
- 接 mock/stub 测试

### 7.3 关键差异

你现在的工具像“一个个独立的小类”；  
`pi-mono` 的工具更像“配置过的能力函数”。

对于后续简化架构来说，`pi-mono` 这种函数工厂更轻；  
但从“先做出来”角度看，你现在这套更直观。

---

## 8. skill 机制：把 skill 当工具 vs 把 skill 当资源

### 8.1 `agent-alpha`

在 `tool_loader.py` 的 `_parse_skill()`：

- 读取 markdown frontmatter
- 生成 `skill__xxx` 这种工具名
- 执行器 `skill_executor()` 直接返回全文

也就是说，在你的项目里：

- skill 会出现在工具列表里
- 模型调用 skill 时，本质是在“调用一个返回说明文档全文的函数”

这是非常直接的做法。

### 8.2 `pi-mono`

在 `learning proj/pi-mono/packages/coding-agent/src/core/skills.ts`：

- `loadSkillsFromDir()`：`146` 行
- `loadSkillFromFile()`：`232` 行
- `formatSkillsForPrompt()`：`290` 行

在 `system-prompt.ts`：

- `buildSystemPrompt()`：`39` 行

这里 skill 的角色不是工具，而是“资源元信息”：

- 先扫描出来
- 放到 prompt 的 `<available_skills>` 中
- 提示模型“如果任务匹配，就用 `read` 去读取 skill 文件”

这跟你的方式差异非常大：

- 你的项目：skill = function tool
- `pi-mono`：skill = prompt 中的索引 + 文件资源

### 8.3 关键差异

你的 skill 方案优点是简单、立即可用；  
`pi-mono` 的优点是更克制，不把所有 skill 正文直接塞进工具调用结果。

从工程边界看，`pi-mono` 这套更干净，因为：

- tool 还是 tool
- 文件还是文件
- skill 只是“什么时候该读哪份文件”的提示层

---

## 9. system prompt 构建：`_build_system_prompt()` vs `_rebuildSystemPrompt() + buildSystemPrompt()`

### 9.1 `agent-alpha`

在 `main.py`：

- `_build_system_prompt()`：`134` 行

它主要靠 Python 字符串模板一次性拼出：

- 工作空间路径
- 输入输出目录
- 大文件分块写策略

优点是非常清楚，读一眼就知道 prompt 长什么样。

问题是：

- prompt 内容和 `Agent` 实例强绑定
- 后面如果要按工具变化、skill 变化、上下文文件变化动态重建，就会越来越重

### 9.2 `pi-mono`

在 `agent-session.ts`：

- `_rebuildSystemPrompt()`：`758` 行

在 `system-prompt.ts`：

- `buildSystemPrompt()`：`39` 行

这套是两段式：

1. `AgentSession` 收集运行时资源
   - 当前工具名
   - tool snippet
   - guideline
   - context files
   - skills
2. `buildSystemPrompt()` 负责纯拼装

这意味着 prompt 不是 `AgentSession` 硬编码出来的，而是“根据当前 runtime 状态重建”。

### 9.3 关键差异

你的 prompt 构建是“对象内模板”；  
`pi-mono` 的 prompt 构建是“纯函数 + 运行时资源”。

这是一个很重要的架构分水岭。

---

## 10. 会话与上下文：`history` 列表 vs `SessionManager` 树结构

### 10.1 `agent-alpha`

核心状态是 `self.history`，定义在 `main.py` `85-86` 行。

相关方法：

- `get_context_json()`：`455` 行
- `save_context()`：`470` 行
- `reset()`：`475` 行
- `save_session_log()`：`480` 行

这个模式的特点是：

- 运行时上下文很直接，就是一个消息数组
- 结束时再把整段历史落成 JSON 日志

优点：

- 好理解
- 调试直观

不足：

- 不支持天然分支
- 不支持“从中间某点继续”
- 压缩后原始上下文不再在活动内存里

### 10.2 `pi-mono`

在 `learning proj/pi-mono/packages/coding-agent/src/core/session-manager.ts`：

- `buildSessionContext()`：`307` 行
- `appendMessage()`：`824` 行
- `appendCompaction()`：`864` 行
- `buildSessionContext()` 实例方法：`1036` 行

这里的核心不是“一个 history 数组”，而是“append-only 的 session entry 树”：

- 每条 entry 有 `id`
- 每条 entry 有 `parentId`
- 当前分支由 `leafId` 决定

`buildSessionContext()` 再负责把这棵树“还原成当前应发给 LLM 的上下文消息”。

这非常关键，因为它意味着：

- 持久化结构和 LLM 上下文结构，不是同一个东西
- 存储层可以很丰富
- 发给模型时再做裁剪和展开

### 10.3 关键差异

`agent-alpha` 的 `history` 既是运行态，也是主要上下文真相。  
`pi-mono` 的 session entries 才是真相，LLM messages 只是投影。

这是 `pi-mono` 架构更稳的一大原因。

---

## 11. 上下文压缩：`ContextManager` vs `AgentSession.compact()`

### 11.1 `agent-alpha`

在 `agent-alpha/agent/core/context_manager.py`：

- `should_compress()`：`99` 行
- `compress_history()`：`121` 行
- `_generate_summary()`：`198` 行

实现思路是：

1. 估算 history token
2. 超阈值就切出 old/recent
3. 用 LLM 生成结构化 JSON 摘要
4. 转成 markdown
5. 用“1 条摘要 + 最近若干轮”替换原历史

这是一个已经相当不错的压缩实现。

### 11.2 `pi-mono`

对应不只一个函数，而是一套配合：

在 `agent-session.ts`：

- `compact()`：`1547` 行
- `_checkCompaction()`：`1683` 行
- `_runAutoCompaction()`：`1765` 行

在 `session-manager.ts`：

- `appendCompaction()`：`864` 行
- `buildSessionContext()`：`307` 行

差异在于：

- `pi-mono` 不是直接改一段内存 `history`
- 它是把 compaction 当成一个正式 session entry 追加进去
- 然后再通过 `buildSessionContext()` 重新构造发给模型的上下文

### 11.3 关键差异

你的压缩是“就地替换活动 history”；  
`pi-mono` 的压缩是“把压缩本身记成历史的一部分，再重新投影上下文”。

这使得 `pi-mono`：

- 更容易保留完整历史
- 更容易回看压缩前后的结构
- 更适合分支和重试

---

## 12. 中断与交互：双 ESC 中断 vs `abort/steer/followUp`

### 12.1 `agent-alpha`

在 `main.py`：

- `_start_esc_listener()`：`278` 行
- `_call_llm_interruptible()`：`303` 行

它的设计是：

- 后台线程检测双 ESC
- 设置 `threading.Event`
- 主循环和工具执行过程中轮询这个事件

这是一个很务实的本地 CLI 方案。

### 12.2 `pi-mono`

底层在 `packages/agent/src/agent.ts`：

- `steer()`：`260` 行
- `followUp()`：`268` 行
- `abort()`：`323` 行

循环层在 `agent-loop.ts`：

- `runLoop()`：`104` 行
- `executeToolCalls()`：`300` 行

上层 `AgentSession.prompt()` 还会根据是否正在 streaming，把用户输入转成：

- 立即执行
- `steer`
- `followUp`

对应位置：

- `agent-session.ts`：`806-945`

### 12.3 关键差异

你的项目里的“中断”主要是停止。  
`pi-mono` 的“中断”已经进化成了三件事：

- 停止
- 中途插话改方向
- 做完这轮后接着处理下一条

所以 `pi-mono` 不只是 interrupt，更像 message queue。

---

## 13. 权限与安全：你的项目更明确

这一块反而是你的项目更“有中心化设计”的地方。

在 `agent-alpha/agent/core/permission_manager.py`：

- `check_permission()`：`49` 行
- `ask_user()`：`229` 行

在 `tool_loader.py`：

- `execute_tool()`：`373` 行里先做 permission check，再决定是否执行

你的优点是：

- 权限规则是一个明确模块
- `deny / allow / ask` 模式很直接
- 会话级缓存也有

`pi-mono` 这里没有一个完全对等的统一 `PermissionManager`。
它更偏向：

- 工具自己负责边界
- mode / extension UI 可以做 confirm
- 交互层支持中断与确认

所以如果只看“权限中心”这件事，你的项目更显性、更好懂。

---

## 14. 我认为最重要的异同

### 14.1 相同点

- 都是典型的 tool-calling agent
- 都重视本地文件/命令工具
- 都有上下文压缩
- 都在往“可扩展 agent”方向走，而不只是一个聊天脚本

### 14.2 最核心的不同点

最本质的不同不是语法语言，也不是工具数量，而是“边界画在哪里”：

- `agent-alpha`：把运行期大部分逻辑集中在 `Agent + ToolLoader + ContextManager`
- `pi-mono`：把这些拆成
  - 底层 `Agent` 引擎
  - 独立 `agentLoop`
  - 上层 `AgentSession`
  - `SessionManager`
  - `ResourceLoader`
  - `tools` 工厂
  - `system-prompt` 纯构建器

换句话说：

- 你的项目更像“一个功能完整的单体 agent 内核”
- `pi-mono` 更像“一个 agent runtime 平台”

---

## 15. 对 `agent-alpha` 最值得借鉴的点

如果后面你继续重构，我觉得最值得借的不是 `pi-mono` 的“所有功能”，而是这 4 个边界感：

1. 把“底层消息循环”和“会话/runtime”分开  
   也就是不要让 `Agent` 一个人同时管状态、循环、交互、持久化。

2. 把“工具创建”和“工具启用策略”分开  
   现在你的 `ToolLoader` 太全能了，后面容易越来越重。

3. 把“存储真相”和“发给模型的上下文”分开  
   `pi-mono` 的 session entry -> session context 这一层非常值得学。

4. 把 prompt 构建变成纯函数  
   这样 skill、tool、context file 的变化都更容易组合。

---

## 16. 结尾判断

如果只问一句“这两个项目最大的区别是什么”，我的答案会是：

`agent-alpha` 擅长把能力快速装到一个 agent 身上；  
`pi-mono` 擅长把 agent 运行时本身做成分层框架。

所以你后面如果要“简化 `agent-alpha`”，真正该借的不是把 `pi-mono` 全搬过来，而是借它的分层方法：

- 哪些是引擎层
- 哪些是会话层
- 哪些是资源层
- 哪些是工具层

这份对比里，最值得反复看的文件我建议是这几组：

- `agent-alpha/agent/core/main.py`
- `learning proj/pi-mono/packages/agent/src/agent.ts`
- `learning proj/pi-mono/packages/agent/src/agent-loop.ts`
- `agent-alpha/agent/core/tool_loader.py`
- `learning proj/pi-mono/packages/coding-agent/src/core/agent-session.ts`
- `learning proj/pi-mono/packages/coding-agent/src/core/session-manager.ts`

