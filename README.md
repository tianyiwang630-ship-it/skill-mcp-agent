# Skills-MCP-Agent-Framework

[English](#english) | [中文](#中文)

---

## 中文

一个支持 MCP Servers 和 Skills 自动发现与集成的智能 Agent 系统。

## 核心功能

### 零配置扩展
- **MCP Servers 自动发现**：将 MCP Server 克隆到 `mcp-servers/` 目录，Agent 自动识别并加载
- **Skills 热插拔**：在 `skills/` 目录创建技能文件夹，立即可用
- **无需修改代码**：添加新工具无需修改 Agent 核心代码或提示词

### 统一工具管理
- **MCP 集成**：支持 STDIO 和 HTTP 两种传输方式，持久连接保持会话状态
- **Python Skills**：从函数签名和 docstring 自动生成 OpenAI 格式工具定义
- **内置工具**：文件读写、Bash 执行、代码编辑等常用工具

### 智能上下文管理
- **自动压缩**：对话历史超过 50% token 限制时，自动压缩旧对话为结构化摘要
- **长期记忆**：保留最近 10 轮完整对话，支持长时间多轮对话
- **Token 预算**：200K 总上下文，智能分配给系统提示、工具定义和对话历史

### 工具搜索机制（Tool Search）
- **按需加载**：垂直工具（如小红书、YouTube）仅在用户查询时加载，节省 token
- **BM25 索引**：基于 BM25 算法实现高效工具搜索
- **智能匹配**：支持中文别名、英文名、工具名称等多种查询方式

### 权限管理系统
- **细粒度控制**：针对不同工具设置不同的权限策略
- **自动降级**：危险操作自动降级为需要用户确认
- **可配置**：通过 `permissions.json` 灵活配置

## 如何配置

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 LLM

编辑 `agent/core/config.py`，设置您的 LLM 配置：

```python
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://your-llm-api.com")
LLM_API_KEY = os.getenv("LLM_API_KEY", "your-api-key")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "your-model-name")
```

或通过环境变量设置：

```bash
export LLM_BASE_URL="https://your-llm-api.com"
export LLM_API_KEY="your-api-key"
export LLM_MODEL_NAME="your-model-name"
```

### 3. 添加 MCP Servers

#### 方式 A：npx 远程包（推荐）

```bash
mkdir mcp-servers/my-server
cat > mcp-servers/my-server/mcp.config.json << EOF
{
  "enabled": true,
  "type": "stdio",
  "command": "npx",
  "args": ["-y", "package-name@latest"],
  "env": {},
  "description": "简要说明"
}
EOF
```

#### 方式 B：克隆 GitHub 项目

```bash
cd mcp-servers
git clone https://github.com/xxx/mcp-server my-server
cd my-server
npm install && npm run build
```

创建 `mcp.config.json`：

```json
{
  "enabled": true,
  "type": "stdio",
  "command": "node",
  "args": ["dist/index.js", "--stdio"],
  "env": {},
  "description": "简要说明"
}
```

#### MCP 分类管理

编辑 `mcp-servers/registry.json` 设置工具分类：

```json
{
  "my-server": {
    "category": "searchable",
    "alias": "我的工具"
  }
}
```

- `core`：常驻工具（如 playwright、open-websearch）
- `searchable`：按需加载（默认）

### 4. 添加 Skills

在 `skills/` 目录创建技能文件夹：

```
skills/
└── my-skill/
    ├── SKILL.md          # 必需：技能元数据和使用指南
    ├── scripts/          # 可选：可执行脚本
    ├── references/       # 可选：参考文档
    └── assets/           # 可选：模板、图标等资源
```

`SKILL.md` 格式：

```markdown
---
name: my-skill
description: 简要描述这个技能的功能和使用场景
---

# My Skill

## 使用方法

具体的使用说明...
```

### 5. 运行 Agent

```python
from agent.core.main import Agent

# 初始化 Agent
agent = Agent()

# 运行对话
response = agent.run("帮我搜索小红书上的化妆品推荐")
print(response)
```

### 6. 配置参数

编辑 `agent/core/config.py` 调整配置：

```python
# 上下文管理
MAX_CONTEXT_TOKENS = 200000      # 总上下文限制
KEEP_RECENT_TURNS = 10           # 保留最近轮次
COMPRESSION_THRESHOLD = 0.5      # 压缩阈值

# 工具执行
MAX_TOOL_RESULT_CHARS = 90000    # 工具结果截断
BASH_TOOL_TIMEOUT = 300          # Bash 超时时间

# LLM 响应
LLM_MAX_TOKENS = 20000           # 默认生成 token 数
```

## 关键实现

### 架构设计

```
Agent Core
├── LLM Client          # LLM API 调用封装
├── Tool Loader         # 统一工具加载器
│   ├── MCP Manager     # MCP 管理器（持久连接）
│   ├── Skills Loader   # Skills 加载器
│   └── Built-in Tools  # 内置工具
├── Context Manager     # 上下文管理器（压缩）
├── Permission Manager  # 权限管理器
└── BM25 Index          # 工具搜索索引
```

### MCP 集成流程

```
1. 扫描 mcp-servers/ 目录
   ↓
2. 识别 server 类型（Node.js/Python/自定义）
   ↓
3. 生成配置（mcp.config.json）
   ↓
4. FastMCP 建立 STDIO 连接
   ↓
5. 获取工具列表（OpenAI format）
   ↓
6. Agent 调用工具（持久会话）
```

**关键文件**：
- [agent/tools/mcp_manager.py](agent/tools/mcp_manager.py) - MCP 管理器实现
- [agent/discovery/mcp_scanner.py](agent/discovery/mcp_scanner.py) - 自动扫描器

### 上下文压缩机制

当对话历史超过可用 token 的 50% 时触发压缩：

```
History: [消息1, 消息2, ..., 消息50]
         ↓
分离: [旧消息: 1-40] + [最近: 41-50]
         ↓
调用 LLM 生成 6 字段摘要
         ↓
重组: [摘要消息] + [最近: 41-50]
```

**摘要结构**：
1. `task_timeline` - 任务时间线
2. `tool_deltas` - 关键工具调用
3. `important_files` - 重要文件清单
4. `current_state` - 当前状态
5. `error_memory` - 错误记忆
6. `critical_user_intents` - 关键用户意图

**关键文件**：
- [agent/core/context_manager.py](agent/core/context_manager.py) - 上下文管理器实现

### Tool Search 机制

垂直工具仅在用户查询时加载：

```
用户: "帮我搜一下小红书上的化妆品推荐"
   ↓
Agent 识别到 "小红书"
   ↓
调用 tool_search("小红书")
   ↓
BM25 索引匹配 → rednote
   ↓
动态加载 rednote 工具
   ↓
Agent 调用 rednote 工具
```

**关键文件**：
- [agent/core/tool_loader.py](agent/core/tool_loader.py) - 工具加载器实现
- [agent/core/bm25.py](agent/core/bm25.py) - BM25 索引实现

### Skills 设计模式

Skills 采用三层加载系统：

1. **元数据**（name + description）- 始终在上下文中（~100 词）
2. **SKILL.md 主体** - 技能触发时加载（<5k 词）
3. **捆绑资源** - 按需加载（无限）

**渐进式披露**：保持 SKILL.md 精简，将详细内容分离到 references 文件夹。

**关键文件**：
- [skills/skill-creator/SKILL.md](skills/skill-creator/SKILL.md) - 技能创建指南

## 项目结构

```
skills-mcp-beta/
├── agent/
│   ├── core/               # 核心模块
│   │   ├── main.py         # Agent 主编排
│   │   ├── llm.py          # LLM 客户端
│   │   ├── tool_loader.py  # 工具加载器
│   │   ├── context_manager.py  # 上下文管理器
│   │   ├── permission_manager.py  # 权限管理器
│   │   ├── bm25.py         # BM25 索引
│   │   └── config.py       # 配置常量
│   ├── tools/              # 内置工具
│   │   ├── mcp_manager.py  # MCP 管理器
│   │   ├── bash_tool.py    # Bash 工具
│   │   ├── read_tool.py    # 文件读取
│   │   ├── write_tool.py   # 文件写入
│   │   ├── edit_tool.py    # 代码编辑
│   │   ├── fetch_tool.py   # 网页抓取
│   │   └── ...
│   └── discovery/          # 自动发现
│       └── mcp_scanner.py  # MCP 扫描器
│
├── mcp-servers/            # MCP Servers 目录
│   ├── registry.json       # MCP 分类注册表
│   ├── playwright/         # 浏览器自动化
│   ├── open-websearch/     # 网页搜索
│   ├── rednote/            # 小红书
│   └── ...
│
├── skills/                 # Skills 目录
│   ├── pdf/                # PDF 处理
│   ├── docx/               # Word 文档
│   ├── pptx/               # PowerPoint
│   ├── xiaohongshu/        # 小红书技能
│   ├── skill-creator/      # 技能创建指南
│   └── ...
│
├── docs/                   # 文档
├── workspace/              # 工作空间
│   ├── demo_*.py          # 演示脚本
│   ├── test_*.py          # 测试脚本
│   └── logs/              # 日志文件
│
├── input files/            # 输入文件目录
├── output files/           # 输出文件目录
├── temp/                   # 临时文件目录
├── requirements.txt        # Python 依赖
└── README.md              # 本文件
```

## 示例用法

### 基础对话

```python
from agent.core.main import Agent

agent = Agent()

# 简单查询
response = agent.run("今天天气怎么样？")

# 复杂任务
response = agent.run("""
帮我完成以下任务：
1. 搜索小红书上关于 Python 学习的笔记
2. 总结前 5 篇笔记的核心内容
3. 生成一份学习计划文档
""")
```

### 使用特定工具

```python
# 小红书搜索
response = agent.run("在小红书搜索'北京旅游攻略'")

# PDF 处理
response = agent.run("读取 report.pdf 中的表格数据")

# 文档编辑
response = agent.run("修改 document.docx 的第二段")
```

### 自定义工作空间

```python
from pathlib import Path
from agent.core.main import Agent

agent = Agent(
    workspace_root="/path/to/workspace",
    max_turns=1000,
    task_id="task-123"
)
```

## 总结

Skills-MCP-Agent-Framework 是一个功能强大、易于扩展的 AI Agent 系统：

- **零配置扩展**：添加 MCP Servers 和 Skills 无需修改核心代码
- **智能工具管理**：自动发现、持久连接、按需加载
- **高效上下文管理**：自动压缩、长期记忆、200K token 支持
- **灵活权限系统**：细粒度控制、自动降级
- **丰富内置能力**：文件操作、代码编辑、网页抓取、Bash 执行

适用于各种 AI Agent 应用场景，从自动化任务到复杂工作流编排。

## 许可证

MIT License - 详见 [LICENSE](LICENSE)

---

## English

An intelligent Agent system with automatic discovery and integration of MCP Servers and Skills.

## Core Features

### Zero-Configuration Extension
- **MCP Servers Auto-Discovery**: Clone MCP Servers to `mcp-servers/` directory, Agent automatically recognizes and loads them
- **Skills Hot-Swap**: Create skill folders in `skills/` directory, immediately available
- **No Code Modification**: Adding new tools requires no changes to Agent core code or prompts

### Unified Tool Management
- **MCP Integration**: Supports both STDIO and HTTP transports with persistent connections
- **Python Skills**: Automatically generates OpenAI format tool definitions from function signatures and docstrings
- **Built-in Tools**: File read/write, Bash execution, code editing, and more

### Intelligent Context Management
- **Auto Compression**: When conversation history exceeds 50% token limit, automatically compresses old conversations into structured summaries
- **Long-term Memory**: Preserves the most recent 10 complete turns for extended multi-turn conversations
- **Token Budget**: 200K total context with intelligent allocation for system prompts, tool definitions, and conversation history

### Tool Search Mechanism
- **On-Demand Loading**: Vertical tools (like Xiaohongshu, YouTube) load only when user queries relevant topics, saving tokens
- **BM25 Indexing**: Efficient tool search based on BM25 algorithm
- **Smart Matching**: Supports Chinese aliases, English names, tool names, and various query methods

### Permission Management System
- **Fine-grained Control**: Set different permission policies for different tools
- **Auto Downgrade**: Dangerous operations automatically downgrade to require user confirmation
- **Configurable**: Flexible configuration via `permissions.json`

## Configuration

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure LLM

Edit `agent/core/config.py`:

```python
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://your-llm-api.com")
LLM_API_KEY = os.getenv("LLM_API_KEY", "your-api-key")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "your-model-name")
```

Or set via environment variables:

```bash
export LLM_BASE_URL="https://your-llm-api.com"
export LLM_API_KEY="your-api-key"
export LLM_MODEL_NAME="your-model-name"
```

### 3. Add MCP Servers

#### Method A: npx Remote Package (Recommended)

```bash
mkdir mcp-servers/my-server
cat > mcp-servers/my-server/mcp.config.json << EOF
{
  "enabled": true,
  "type": "stdio",
  "command": "npx",
  "args": ["-y", "package-name@latest"],
  "env": {},
  "description": "Brief description"
}
EOF
```

#### Method B: Clone GitHub Project

```bash
cd mcp-servers
git clone https://github.com/xxx/mcp-server my-server
cd my-server
npm install && npm run build
```

Create `mcp.config.json`:

```json
{
  "enabled": true,
  "type": "stdio",
  "command": "node",
  "args": ["dist/index.js", "--stdio"],
  "env": {},
  "description": "Brief description"
}
```

#### MCP Category Management

Edit `mcp-servers/registry.json`:

```json
{
  "my-server": {
    "category": "searchable",
    "alias": "My Tool"
  }
}
```

- `core`: Resident tools (e.g., playwright, open-websearch)
- `searchable`: On-demand loading (default)

### 4. Add Skills

Create skill folders in `skills/` directory:

```
skills/
└── my-skill/
    ├── SKILL.md          # Required: Skill metadata and usage guide
    ├── scripts/          # Optional: Executable scripts
    ├── references/       # Optional: Reference documentation
    └── assets/           # Optional: Templates, icons, etc.
```

`SKILL.md` format:

```markdown
---
name: my-skill
description: Brief description of this skill's functionality and use cases
---

# My Skill

## Usage

Detailed usage instructions...
```

### 5. Run Agent

```python
from agent.core.main import Agent

# Initialize Agent
agent = Agent()

# Run conversation
response = agent.run("Help me search for cosmetic recommendations on Xiaohongshu")
print(response)
```

### 6. Configure Parameters

Edit `agent/core/config.py`:

```python
# Context Management
MAX_CONTEXT_TOKENS = 200000      # Total context limit
KEEP_RECENT_TURNS = 10           # Keep recent turns
COMPRESSION_THRESHOLD = 0.5      # Compression threshold

# Tool Execution
MAX_TOOL_RESULT_CHARS = 90000    # Tool result truncation
BASH_TOOL_TIMEOUT = 300          # Bash timeout

# LLM Response
LLM_MAX_TOKENS = 20000           # Default generation tokens
```

## Key Implementation

### Architecture Design

```
Agent Core
├── LLM Client          # LLM API call wrapper
├── Tool Loader         # Unified tool loader
│   ├── MCP Manager     # MCP manager (persistent connection)
│   ├── Skills Loader   # Skills loader
│   └── Built-in Tools  # Built-in tools
├── Context Manager     # Context manager (compression)
├── Permission Manager  # Permission manager
└── BM25 Index          # Tool search index
```

### MCP Integration Flow

```
1. Scan mcp-servers/ directory
   ↓
2. Identify server type (Node.js/Python/Custom)
   ↓
3. Generate configuration (mcp.config.json)
   ↓
4. FastMCP establishes STDIO connection
   ↓
5. Get tool list (OpenAI format)
   ↓
6. Agent calls tools (persistent session)
```

**Key Files**:
- [agent/tools/mcp_manager.py](agent/tools/mcp_manager.py) - MCP manager implementation
- [agent/discovery/mcp_scanner.py](agent/discovery/mcp_scanner.py) - Auto scanner

### Context Compression Mechanism

Triggers when conversation history exceeds 50% of available tokens:

```
History: [Message1, Message2, ..., Message50]
         ↓
Split: [Old: 1-40] + [Recent: 41-50]
         ↓
Call LLM to generate 6-field summary
         ↓
Reassemble: [Summary] + [Recent: 41-50]
```

**Summary Structure**:
1. `task_timeline` - Task timeline
2. `tool_deltas` - Key tool calls
3. `important_files` - Important files list
4. `current_state` - Current state
5. `error_memory` - Error memory
6. `critical_user_intents` - Critical user intents

**Key Files**:
- [agent/core/context_manager.py](agent/core/context_manager.py) - Context manager implementation

### Tool Search Mechanism

Vertical tools load only when user queries relevant topics:

```
User: "Help me search for cosmetic recommendations on Xiaohongshu"
   ↓
Agent recognizes "Xiaohongshu"
   ↓
Call tool_search("Xiaohongshu")
   ↓
BM25 index match → rednote
   ↓
Dynamically load rednote tools
   ↓
Agent calls rednote tools
```

**Key Files**:
- [agent/core/tool_loader.py](agent/core/tool_loader.py) - Tool loader implementation
- [agent/core/bm25.py](agent/core/bm25.py) - BM25 index implementation

### Skills Design Pattern

Skills use a three-tier loading system:

1. **Metadata** (name + description) - Always in context (~100 words)
2. **SKILL.md body** - Loads when skill triggers (<5k words)
3. **Bundled resources** - Loads on demand (unlimited)

**Progressive Disclosure**: Keep SKILL.md concise, separate detailed content into references folder.

**Key Files**:
- [skills/skill-creator/SKILL.md](skills/skill-creator/SKILL.md) - Skill creation guide

## Project Structure

```
skills-mcp-beta/
├── agent/
│   ├── core/               # Core modules
│   │   ├── main.py         # Agent main orchestration
│   │   ├── llm.py          # LLM client
│   │   ├── tool_loader.py  # Tool loader
│   │   ├── context_manager.py  # Context manager
│   │   ├── permission_manager.py  # Permission manager
│   │   ├── bm25.py         # BM25 index
│   │   └── config.py       # Configuration constants
│   ├── tools/              # Built-in tools
│   │   ├── mcp_manager.py  # MCP manager
│   │   ├── bash_tool.py    # Bash tool
│   │   ├── read_tool.py    # File read
│   │   ├── write_tool.py   # File write
│   │   ├── edit_tool.py    # Code edit
│   │   ├── fetch_tool.py   # Web fetch
│   │   └── ...
│   └── discovery/          # Auto discovery
│       └── mcp_scanner.py  # MCP scanner
│
├── mcp-servers/            # MCP Servers directory
│   ├── registry.json       # MCP category registry
│   ├── playwright/         # Browser automation
│   ├── open-websearch/     # Web search
│   ├── rednote/            # Xiaohongshu
│   └── ...
│
├── skills/                 # Skills directory
│   ├── pdf/                # PDF processing
│   ├── docx/               # Word documents
│   ├── pptx/               # PowerPoint
│   ├── xiaohongshu/        # Xiaohongshu skill
│   ├── skill-creator/      # Skill creation guide
│   └── ...
│
├── docs/                   # Documentation
├── workspace/              # Workspace
│   ├── demo_*.py          # Demo scripts
│   ├── test_*.py          # Test scripts
│   └── logs/              # Log files
│
├── input files/            # Input files directory
├── output files/           # Output files directory
├── temp/                   # Temp files directory
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## Example Usage

### Basic Conversation

```python
from agent.core.main import Agent

agent = Agent()

# Simple query
response = agent.run("What's the weather today?")

# Complex task
response = agent.run("""
Help me complete the following tasks:
1. Search for Python learning notes on Xiaohongshu
2. Summarize the core content of the top 5 notes
3. Generate a study plan document
""")
```

### Using Specific Tools

```python
# Xiaohongshu search
response = agent.run("Search for 'Beijing travel guide' on Xiaohongshu")

# PDF processing
response = agent.run("Read table data from report.pdf")

# Document editing
response = agent.run("Modify the second paragraph of document.docx")
```

### Custom Workspace

```python
from pathlib import Path
from agent.core.main import Agent

agent = Agent(
    workspace_root="/path/to/workspace",
    max_turns=1000,
    task_id="task-123"
)
```

## Summary

Skills-MCP-Agent-Framework is a powerful, easily extensible AI Agent system:

- **Zero-Configuration Extension**: Add MCP Servers and Skills without modifying core code
- **Intelligent Tool Management**: Auto-discovery, persistent connections, on-demand loading
- **Efficient Context Management**: Auto compression, long-term memory, 200K token support
- **Flexible Permission System**: Fine-grained control, auto downgrade
- **Rich Built-in Capabilities**: File operations, code editing, web fetching, Bash execution

Suitable for various AI Agent application scenarios, from automated tasks to complex workflow orchestration.

## License

MIT License - See [LICENSE](LICENSE)
