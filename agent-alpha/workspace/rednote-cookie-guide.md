# 小红书 Cookie 获取指南

## 为什么需要 Cookie？

RedNote-MCP 需要你的小红书登录凭证才能：
- 搜索笔记内容
- 获取笔记详情
- 查看评论

Cookie 是你登录后浏览器保存的凭证，**不需要提供账号密码**。

---

## 方法 1：Chrome/Edge 浏览器获取（推荐）

### 步骤

1. **打开小红书网页版**
   - 访问：https://www.xiaohongshu.com
   - 登录你的账号

2. **打开开发者工具**
   - 按 `F12` 或 `Ctrl + Shift + I`
   - 或右键点击页面 → "检查"

3. **切换到 Application 标签**
   - 在开发者工具顶部找到 `Application` 标签
   - 点击进入

4. **找到 Cookies**
   - 左侧栏展开 `Storage` → `Cookies`
   - 点击 `https://www.xiaohongshu.com`

5. **复制 Cookie**
   - 找到名为 `a1` 的 cookie（重要！）
   - 找到名为 `web_session` 的 cookie（重要！）
   - **有两种复制方式**：

   **方式 A - 只复制关键值**（推荐，更安全）：
   ```
   a1=你的a1值; web_session=你的web_session值
   ```

   **方式 B - 复制完整 Cookie**：
   - 点击开发者工具左上角的 "Network" 标签
   - 刷新页面（F5）
   - 点击第一个请求 `www.xiaohongshu.com`
   - 右侧找到 `Request Headers` → `Cookie`
   - 复制整个 Cookie 字符串

6. **粘贴到配置文件**
   - 打开：`mcp-servers/rednote/mcp.config.json`
   - 把 Cookie 粘贴到 `XHS_COOKIE` 字段
   - 把 `"enabled": false` 改为 `"enabled": true`

---

## 方法 2：使用浏览器扩展（更简单）

### EditThisCookie 扩展

1. **安装扩展**
   - Chrome: https://chrome.google.com/webstore/detail/editthiscookie/
   - Edge: https://microsoftedge.microsoft.com/addons/detail/edit-this-cookie/

2. **获取 Cookie**
   - 登录小红书网页版
   - 点击浏览器工具栏的 Cookie 图标
   - 点击 "Export" → 导出为 JSON 格式
   - 复制内容

3. **转换为配置格式**
   ```json
   "a1=xxx; web_session=yyy; 其他key=值..."
   ```

---

## 方法 3：浏览器开发者工具 - Console 方法

1. **打开小红书并登录**
   - https://www.xiaohongshu.com

2. **打开 Console**
   - F12 → `Console` 标签

3. **输入命令并回车**
   ```javascript
   document.cookie
   ```

4. **复制输出的字符串**
   - 这就是完整的 Cookie
   - 直接粘贴到配置文件

---

## 配置文件示例

配置完成后，`mcp-servers/rednote/mcp.config.json` 应该像这样：

```json
{
  "enabled": true,
  "type": "stdio",
  "command": "npx",
  "args": ["-y", "@ifuryst/rednote-mcp@latest"],
  "env": {
    "XHS_COOKIE": "a1=18c123abc456def789; web_session=040062abc123def456; webId=abc123def456; webBuild=4.0.0"
  },
  "description": "RedNote(Xiaohongshu) MCP - 小红书内容搜索、笔记获取、评论查看"
}
```

**注意**：
- Cookie 是一段很长的字符串
- 不要保留外层的引号
- 确保整个 Cookie 在一行内

---

## 验证 Cookie 是否有效

配置好后，运行测试脚本验证：

```bash
cd d:/files/demo/skills-mcp-beta
conda activate ai12
PYTHONIOENCODING=utf-8 python workspace/test_rednote.py
```

如果看到小红书搜索结果，说明 Cookie 有效！

---

## Cookie 过期处理

小红书 Cookie 通常有效期为 **7-30 天**。

**过期症状**：
- 测试返回 "登录已过期"
- 搜索结果为空

**解决方法**：重新按上述步骤获取新 Cookie，更新配置文件。

---

## 安全提示

- ⚠️ **不要分享你的 Cookie** — 相当于你的登录凭证
- ⚠️ **不要提交到 Git** — `.config.json` 已在 `.gitignore` 中
- ✅ Cookie 只存在本地，只传给小红书官方服务器
- ✅ 可以随时更换/撤销（重新登录即可）

---

## 获取 Cookie 后

1. 更新 `mcp-servers/rednote/mcp.config.json`
2. 设置 `"enabled": true`
3. 运行 `python workspace/test_rednote.py` 测试

测试通过后，你的 Agent 就能：
- 🔍 搜索小红书笔记
- 📄 获取笔记完整内容
- 💬 查看评论

---

**准备好 Cookie 后，告诉我，我会帮你完成测试！**
