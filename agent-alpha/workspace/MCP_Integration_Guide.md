# MCP 集成指南

本文档记录已集成的 MCP servers 及其配置、使用方式。

---

## 已集成的 MCP Servers

| Server | 工具数 | 用途 | 状态 |
|--------|-------|------|------|
| **open-websearch** | 5 | 多引擎网页搜索 | ✅ 已集成 |
| **playwright** | 22 | 浏览器自动化（JS渲染） | ✅ 已集成 |
| **ytb** | - | YouTube 视频摘要 | ✅ 已集成 |

---

## 1. open-websearch

### 配置文件
**位置**: `mcp-servers/open-websearch/mcp.config.json`

```json
{
  "enabled": true,
  "type": "stdio",
  "command": "npx",
  "args": ["-y", "open-websearch@latest"],
  "env": {
    "DEFAULT_SEARCH_ENGINE": "duckduckgo",
    "MODE": "stdio"
  },
  "description": "Multi-engine web search (Bing, DuckDuckGo, Exa, Brave, Baidu, etc.)"
}
```

### 关键说明
- **默认搜索引擎**: DuckDuckGo（Bing 有反爬限制会返回 403）
- **工作方式**: NPX 远程包，无需本地安装
- **提供的工具**（5个）:
  - 多引擎搜索（Bing, DuckDuckGo, Baidu, Brave, Exa）
  - 返回搜索结果摘要和链接

### 适用场景
- 获取最新信息、新闻
- 查找网站链接
- 事实类查询（USC 校长、历史事件等）

### 局限性
- **无法直接获取实时数据**（如股价）— 搜索结果只有摘要，真实数据在页面内部
- 需要配合 `fetch` 或 `playwright` 工具获取页面详情

---

## 2. playwright

### 配置文件
**位置**: `mcp-servers/playwright/mcp.config.json`

```json
{
  "enabled": true,
  "type": "stdio",
  "command": "npx",
  "args": ["@playwright/mcp@latest", "--headless"],
  "env": {},
  "description": "Playwright browser automation - 浏览器自动化，支持 JS 渲染页面的内容获取"
}
```

### 浏览器安装
**位置**: `C:\Users\20157\AppData\Local\ms-playwright\chromium-1208` (173MB)

**安装命令**:
```bash
npx playwright install chromium
```

### 核心能力
- **JS 渲染支持** — 能够处理 SPA 页面（Yahoo Finance、Google Finance 等）
- **无需视觉模型** — 返回可访问性树（结构化文本），不依赖截图
- **持久会话** — 支持多标签、保持登录状态

### 提供的工具（22个，无 vision 模式）

#### 核心导航
- `browser_navigate` — 打开 URL
- `browser_navigate_back` — 后退
- `browser_close` — 关闭页面
- `browser_tabs` — 标签页管理

#### 页面内容获取
- `browser_snapshot` — **核心工具** — 获取页面可访问性树（纯文本结构）
- `browser_console_messages` — 控制台日志
- `browser_network_requests` — 网络请求列表

#### 交互操作
- `browser_click` — 点击元素
- `browser_type` — 输入文本
- `browser_fill_form` — 批量填表
- `browser_select_option` — 下拉选择
- `browser_hover` — 悬停
- `browser_drag` — 拖拽
- `browser_press_key` — 按键

#### JavaScript 执行
- `browser_evaluate` — 在页面中执行 JS 代码（可直接提取数据）
- `browser_run_code` — 运行 Playwright 代码片段

#### 其他
- `browser_file_upload` — 上传文件
- `browser_handle_dialog` — 处理弹窗
- `browser_resize` — 调整窗口大小
- `browser_wait_for` — 等待元素/文本出现
- `browser_install` — 安装浏览器
- `browser_take_screenshot` — 截图（默认禁用，需 `--caps vision`）

### 模式切换

#### 当前模式：纯文本（无 vision）
```json
"args": ["@playwright/mcp@latest", "--headless"]
```
- 只暴露基于文本的工具（snapshot、evaluate、click 等）
- 不涉及图像处理，适配当前 LLM

#### 未来多模态模式
```json
"args": ["@playwright/mcp@latest", "--headless", "--caps", "vision"]
```
- 额外暴露截图相关工具（screenshot、坐标点击等）
- 需要支持图像处理的 LLM

### 适用场景
- **SPA 页面抓取** — Yahoo Finance、Google Finance 等 JS 渲染页面
- **需要交互的任务** — 登录、填表、多步操作
- **动态内容提取** — 用 `evaluate` 直接在页面执行 JS 提取数据

### 与 fetch 工具对比

| | fetch (内置工具) | Playwright MCP |
|---|---|---|
| **SPA/JS页面** | ❌ 返回空壳 | ✅ 完整渲染 |
| **速度** | 毫秒级 | 秒级（启动浏览器） |
| **依赖** | 零依赖 | 需 Chromium (~173MB) |
| **Token消耗** | 低（一次调用） | 高（navigate + snapshot） |
| **适用场景** | 静态页面、API、新闻 | JS页面、需登录、金融数据 |

### 推荐工作流

```
search (open-webSearch)
  ↓
判断页面类型
  ├─ 静态页面/新闻 → fetch（快速、省token）
  └─ SPA/动态页面 → Playwright navigate → snapshot/evaluate
```

---

## 3. ytb (YouTube Video Summarizer)

### 配置文件
**位置**: `mcp-servers/ytb/mcp.config.json`

```json
{
  "enabled": true,
  "type": "stdio",
  "command": "npx",
  "args": ["-y", "youtube-video-summarizer-mcp"],
  "env": {},
  "description": "YouTube video summarization"
}
```

### 关键说明
- NPX 远程包
- 提供 YouTube 视频摘要功能

---

## 系统架构

### MCP 自动发现机制

**扫描器**: `agent/discovery/mcp_scanner.py`

**扫描路径**: `mcp-servers/` 目录

**检测优先级**:
1. `mcp.config.json` （最高优先级，手动配置）
2. `package.json` （Node.js 项目）
3. `pyproject.toml` （Python 项目）
4. 可执行文件

### MCP 管理器

**文件**: `agent/tools/mcp_manager.py`

**特点**:
- **持久连接** — 后台事件循环保持所有 MCP server 连接
- **自动发现** — 初始化时扫描并连接所有 enabled 的 server
- **STDIO wrapper** — 自动过滤 npx 的非 JSON-RPC 输出

**API**:
```python
manager = MCPManager()  # 自动连接所有 server

# 获取所有工具
tools = manager.get_all_tools()

# 调用工具（工具名格式：mcp__<server>__<tool>）
result = manager.call_tool("mcp__playwright__browser_navigate", {
    "url": "https://example.com"
})

# 关闭
manager.close_all()
```

### 工具命名规范

- **MCP 工具**: `mcp__<server>__<tool>` （如 `mcp__playwright__browser_snapshot`）
- **Skill 工具**: `skill__<name>` （如 `skill__commit`）
- **内置工具**: 直接名称（如 `fetch`, `bash`, `read`）

---

## 内置 fetch 工具

### 文件
**位置**: `agent/tools/fetch_tool.py`

### 功能
- 获取 URL 内容，返回干净的纯文本
- 自动清理 HTML/XML 标签、脚本、样式、导航、JSON-LD 等噪音
- 默认最大长度 5000 字符，可调整

### 定义
```python
{
    "name": "fetch",
    "description": "获取指定 URL 的网页内容...",
    "parameters": {
        "url": "string",
        "max_length": "integer (default: 5000)"
    }
}
```

### 局限性
- **无法处理 SPA 页面** — 依赖 `urllib`，不执行 JavaScript
- Yahoo Finance、Google Finance 等返回空壳
- 推荐使用 Playwright 处理此类页面

### 权限控制
- **默认权限**: `allow`（只读工具，自动允许）
- **会话缓存**: 选 [Y] 后整个会话的 fetch 调用都不再询问

---

## 权限管理改进

### 文件
**位置**: `agent/core/permission_manager.py`

### 问题修复（2026-02-08）

#### 问题 1：fetch 每次都要授权
**根因**: `_get_signature` 为 fetch 生成唯一签名（包含 URL），每个 URL 都触发新询问

**修复**:
```python
elif tool == "fetch":
    # 用工具名作为签名，一次授权覆盖所有 URL
    return tool
```

#### 问题 2：fetch 默认需要询问
**根因**: `_get_default_permission` 未将 fetch 列为只读工具

**修复**:
```python
if tool in ["read", "glob", "grep", "fetch"]:
    return "allow"
```

### 当前行为
- `fetch` 工具默认自动允许（与 read、glob 同级）
- 选择 [Y] 后，整个会话的 fetch 调用都不再询问
- MCP 工具同理（一次授权覆盖所有调用）

---

## 测试脚本

### open-webSearch 测试
**文件**: `workspace/test_websearch.py`

**测试内容**:
- 连接验证
- 工具发现
- DuckDuckGo 搜索

### Playwright 测试
**文件**: `workspace/test_playwright.py`

**测试内容**:
- 工具发现（22个）
- example.com 基础导航 + snapshot
- Yahoo Finance SPA 页面渲染（验证 JS 支持）

---

## 环境要求

### Python 环境
- **conda 环境**: `ai12`
- **必需库**: `fastmcp`, `beautifulsoup4`, `lxml`

### Node.js
- **npx** 已安装（用于运行远程 MCP 包）

### 编码
- **Windows**: `PYTHONIOENCODING=utf-8`（避免 GBK 编码错误）

---

## 常见问题

### Q: Chromium 安装在哪里？
**A**: `C:\Users\<用户名>\AppData\Local\ms-playwright\chromium-1208`
- 不影响系统已有的 Chrome/Edge
- 卸载只需删除文件夹
- 也可用 `--browser msedge` 使用系统 Edge

### Q: 如何切换到多模态模式？
**A**: 修改 `mcp-servers/playwright/mcp.config.json`:
```json
"args": ["@playwright/mcp@latest", "--headless", "--caps", "vision"]
```
重启 Agent 即可，工具列表会自动增加 screenshot 等工具。

### Q: 为什么 fetch 返回空？
**A**: 目标页面可能是 SPA（需 JS 渲染），改用 Playwright:
```
search → 拿到 URL → playwright navigate + snapshot
```

### Q: MCP 工具太多占用上下文怎么办？
**A**: 你的系统是动态加载，影响不大。如需优化可：
- 在 `mcp.config.json` 中设置 `"enabled": false` 禁用不需要的 server
- 只在需要时启用特定 server

---

## 更新日志

### 2026-02-08
- ✅ 集成 open-webSearch MCP（DuckDuckGo 搜索）
- ✅ 创建内置 fetch 工具（HTML/XML 清理）
- ✅ 修复权限管理器（fetch 工具会话缓存）
- ✅ 集成 Playwright MCP（浏览器自动化）
- ✅ 安装 Chromium 浏览器（173MB）
- ✅ 验证 SPA 页面渲染能力（Yahoo Finance 测试通过）

---

**文档版本**: 1.0
**最后更新**: 2026-02-08
**维护者**: Agent System
