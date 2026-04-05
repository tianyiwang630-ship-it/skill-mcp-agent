# RedNote MCP 全面重构方案

## 设计理念
MCP 是纯数据采集工具，AI 自己决定探索路径。提供细粒度的工具覆盖：人、内容、社交、收藏。

## 工具清单（7 个）

### 1. `search_notes(keywords, limit)` — 保留，小改
- 过滤掉空条目（title 和 url 都为空的）
- 返回不变：标题、作者、点赞、链接

### 2. `get_user_profile(username)` — **新工具**，从 get_user_notes 拆分
- 导航到用户主页，提取完整 profile：
  - 用户名、小红书号 (red ID)、简介/签名 (bio)
  - IP 属地、性别、认证信息、标签
  - 关注数、粉丝数、获赞与收藏数
  - 笔记总数
  - 主页 URL
- 不返回笔记列表（那是 get_user_notes 的事）
- 导航策略：搜索用户名 → 找到用户卡片 → 进入主页（复用现有 getUserNotes 的用户查找逻辑）

### 3. `get_user_notes(username, limit)` — 改造
- 保持现有导航逻辑（搜索用户名 → 进入主页）
- 只返回笔记列表，不再返回 profile 详情（profile 由 get_user_profile 负责）
- 如果页面已经在该用户主页（检测 URL 包含 /user/profile/），直接提取，不重新搜索

### 4. `get_user_collections(username)` — **新工具**
- 导航到用户主页 → 点击"收藏"标签
- 提取公开收藏夹列表：名称、封面、笔记数量、收藏夹 URL/ID
- 如果没有公开收藏夹，返回空列表 + 提示

### 5. `get_collection_notes(username, collection_name, limit)` — **新工具**
- 导航到用户主页 → 点击"收藏"标签 → 点击指定收藏夹
- 提取收藏夹内的笔记列表：标题、作者、链接
- 参数用 collection_name（收藏夹名称）而非 URL，因为 AI 从 get_user_collections 拿到名称后直接传

### 6. `get_note_content(url)` — 保留，增强提取
- 在 noteDetail.ts 中增加：收藏数、分享数（如果页面有的话）
- 保持 3-tier 点击策略不变

### 7. `get_note_comments(url)` — 保留不变

### 8. `login()` — 保留不变

## 文件改动

### `src/tools/rednoteTools.ts`
1. **新增 `getUserProfile(username)`**：
   - 复用现有的"搜索用户 → 进入主页"导航逻辑（抽取为 `private navigateToUserProfile(username)`）
   - `page.evaluate` 全面提取 profile DOM：
     - `.user-name` — 用户名
     - `.user-desc` / `[class*="desc"]` — 简介
     - `.user-redId` / `[class*="redId"]` / 包含"小红书号"的文本节点 — red ID
     - `.tag-item` / `[class*="tag"]` — 标签
     - `.ip-container` / `[class*="ip"]` — IP 属地
     - `[class*="gender"]` — 性别
     - `[class*="verify"]` / `.verify-info` — 认证
     - 复用现有 stats regex（关注/粉丝/获赞）
   - 选择器用 fallback 链：先精确选择器，再模糊选择器，再文本搜索

2. **抽取 `private navigateToUserProfile(username): Promise<string>`**：
   - 从现有 `getUserNotes` 中提取搜索用户 + 进入主页的通用逻辑
   - 返回 profile URL
   - 被 `getUserProfile`, `getUserNotes`, `getUserCollections` 共用
   - 优化：如果当前页面已经在目标用户主页，跳过导航

3. **新增 `getUserCollections(username)`**：
   - 调用 `navigateToUserProfile(username)`
   - 点击"收藏"标签（`page.click` 匹配含"收藏"文本的 tab）
   - 等待收藏夹列表加载
   - `page.evaluate` 提取收藏夹卡片信息

4. **新增 `getCollectionNotes(username, collectionName, limit)`**：
   - 调用 `navigateToUserProfile(username)`
   - 点击"收藏"标签
   - 在收藏夹列表中找到匹配名称的收藏夹并点击
   - 提取笔记列表

5. **改造 `getUserNotes`**：
   - 用 `navigateToUserProfile` 替代内联的导航逻辑
   - 只返回笔记列表（移除 profile stats）

6. **改造 `searchNotes`**：
   - 返回前过滤空条目：`notes.filter(n => n.title && n.url)`

### `src/tools/noteDetail.ts`
- 增加收藏数提取：`.interact-container .collect-wrapper .count` 或类似选择器
- 增加到 `NoteDetail` interface

### `src/cli.ts`
- 注册新的 3 个工具：`get_user_profile`, `get_user_collections`, `get_collection_notes`
- 修改 `get_user_notes` 的返回格式（不含 profile info）
- 工具描述要清晰告诉 AI 每个工具提供什么数据

## 注意事项
- 所有新工具都要 `acquireLock()` + `finally { lock.release() }`
- 所有 `page.goto` 用 `{ waitUntil: 'domcontentloaded' }`
- Profile 页面可能不需要 xsec_token（直接 goto profile URL 通常可行）
- CSS 选择器不确定的地方，用 fallback 链 + 日志记录实际匹配到什么
- 收藏夹标签可能用 tab 切换实现，需要在浏览器中点击（非 page.goto）
