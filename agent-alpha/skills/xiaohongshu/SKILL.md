---
name: xiaohongshu
description: 小红书（RedNote/XHS）浏览与信息提取。当用户需要搜索小红书笔记、查看用户主页、阅读笔记内容、查看评论/点赞/收藏等操作时使用。读取本 skill 后，立即调用 tool_search 加载 rednote 工具。
---

# 小红书浏览技能

## 第一步：加载工具

读到这里后，**立即调用 `tool_search(query="rednote")` 加载小红书 MCP 工具**，然后再执行用户任务。不要重复调用本 skill。

## 使用要点

### 点击 > 直接导航

小红书的反爬机制使用 xsec_token（由 JS 点击事件注入，不在 HTML href 中）。**务必用 click 工具点击链接进入笔记**，不要用 browse 直接访问笔记 URL。

正确：search → 快照中找到目标 → click("笔记标题")
错误：browse("https://www.xiaohongshu.com/explore/6789...")  ← 被拦截

### 快照是你的眼睛

每个工具调用返回页面快照（Links、Buttons、Inputs、Page Content）。根据快照决定下一步。

### 搜索用户时用 type="user"

搜索用户名默认搜笔记，要搜用户本人需传 type="user"。

## 注意事项

- **不要并行调用多个工具** — 浏览器共享单例，有互斥锁
- **遇到登录弹窗** — 调用 login 工具让用户扫码
- **页面加载慢** — 用 snapshot 重新获取
- **IP风控** — 看到"安全限制"提示，告知用户稍后重试
