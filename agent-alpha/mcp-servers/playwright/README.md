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
  - 在有头模式运行中定时同步导出共享 `storage-state`
  - 在有头模式关闭前再补一次同步导出共享 `storage-state`

- `state/profiles/default/`
  持久浏览器 profile 目录。
  单 agent、有头、人工登录时主要使用这里。

- `state/storage/shared.json`
  共享登录态文件。
  由有头模式运行中定时自动导出，并在关闭前再补一次导出。
  以后多 agent、无头模式主要读取这份文件。

## 如何手动清理历史记录

如果想手动清掉 Playwright 有头模式留下的浏览器历史记录、缓存和本地 profile，可以这样做：

1. 先关闭正在运行的 Playwright 浏览器。
2. 删除 `agent-alpha/mcp-servers/playwright/state/profiles/default/` 这个目录。
3. 下次再启动有头模式时，系统会自动重建一个新的干净 profile。

说明：
- 这样会清掉浏览器历史记录、缓存和当前 profile 里的本地状态。
- `state/storage/shared.json` 不会自动删除，所以共享登录态默认还在。
- 如果你连共享登录态也想一起清掉，再手动删除 `state/storage/shared.json`。

## 两种模式

### 1. Headed

配置文件：[playwright.headed.config.json](/d:/files/demo/0312-newagent/agent-alpha/mcp-servers/playwright/playwright.headed.config.json)

特点：
- `headless: false`
- 使用持久 profile
- 适合人工登录、验证码、风控确认
- 运行中每隔一段时间自动把当前 `storage-state` 写到 `state/storage/shared.json`
- 关闭浏览器前会再补一次保存，尽量避免手动关窗口时丢失登录态

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
