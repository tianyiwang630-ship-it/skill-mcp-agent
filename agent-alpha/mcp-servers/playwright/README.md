# Playwright MCP

这个目录使用官方 `@playwright/mcp` 包，但不是直接裸跑官方命令，而是加了一层本地 wrapper。

## 当前约定

- 默认入口是 [mcp.config.json](/d:/files/demo/0312-newagent/agent-alpha/mcp-servers/playwright/mcp.config.json)
- 默认模式是有头：`playwright.headed.config.json`
- 未来多 agent 可切到无头：`playwright.headless.config.json`
- 浏览器二进制安装在 Playwright 默认全局目录
- 本地目录只保存 wrapper、配置和登录态

## 目录说明

```text
playwright/
  mcp.config.json
  server.js
  playwright.headed.config.json
  playwright.headless.config.json
  state/
    profiles/
      default/
    storage/
      shared.json
```

- `server.js`
  本地 MCP wrapper。继续使用官方 Playwright MCP 工具集，只额外负责：
  - 选择 headed / headless 配置
  - 在有头模式关闭前同步导出共享 `storage-state`

- `state/profiles/default/`
  持久浏览器 profile 目录。
  单 agent、有头、人工登录时主要使用这里。

- `state/storage/shared.json`
  共享登录态文件。
  由有头模式在关闭浏览器前自动导出。
  以后多 agent、无头模式主要读取这份文件。

## 两种模式

### 1. Headed

配置文件：[playwright.headed.config.json](/d:/files/demo/0312-newagent/agent-alpha/mcp-servers/playwright/playwright.headed.config.json)

特点：
- `headless: false`
- 使用持久 profile
- 适合人工登录、验证码、风控确认
- 关闭浏览器前自动把当前完整 `storage-state` 写到 `state/storage/shared.json`

### 2. Headless

配置文件：[playwright.headless.config.json](/d:/files/demo/0312-newagent/agent-alpha/mcp-servers/playwright/playwright.headless.config.json)

特点：
- `headless: true`
- `isolated: true`
- 启动时读取 `state/storage/shared.json`
- 适合以后多 agent 并发复用登录态

## 当前默认行为

现在 [mcp.config.json](/d:/files/demo/0312-newagent/agent-alpha/mcp-servers/playwright/mcp.config.json) 默认指向有头模式：

```json
{
  "command": "node",
  "args": ["server.js", "--config", "playwright.headed.config.json"]
}
```

如果以后要切到无头共享登录态，只需要把配置文件名换成：

```json
"playwright.headless.config.json"
```

## 浏览器安装位置

浏览器二进制不放在这个目录里，默认安装在 Playwright 全局目录。

Windows 常见位置：

```text
C:\Users\<用户名>\AppData\Local\ms-playwright
```

这符合当前项目约定：
- 浏览器装全局
- 状态留本地

## 已确认可用

当前这套目录已经完成过两类验证：

- Python 侧测试通过，确认目录结构和配置能被 MCP 扫描识别
- 本地真实启动验证通过，确认有头 Chromium 可以正常拉起并关闭
