1 我不懂代码，你和我交流要用我能理解的表达方式
2 执行前，必须和我讨论1-3轮，收束边界才能执行
3 后端接口使用fastapi库，遵循RESTFUL api的规范。
4 代码风格要简洁，如无必要毋增实体；代码要清晰，注重模块化和可扩展性。
5 中间产物放进temp文件夹，尤其是pytest
6 项目有更改，功能迭代、架构调整、bug修复等要写到开发日志.md里，记录日期、背景和关键更改内容，但是没改项目就不要记
7 阅读中文内容，用utf-8

#背景知识
learning proj是用来学习和借鉴的项目文件夹。目前包含skill-mcp-agent、nanobot、pi-mono、openclaw、learn-claude-code、claw-code和playwright。其中，skill-mcp-agent是我之前的项目；nanobot是openclaw的轻量化实现；pi-mono是极简的agent框架；learn-claude-code和claw-code是用来拆解、学习claudecode实现思路的项目；playwright用于浏览器自动化相关能力的学习和实验。
agent-alpha是现在focus的项目，希望能够简化skill-mcp-agent（agent-alpha内容就是skill-mcp-agent复制来的），并借鉴learning proj中的pi-mono、nanobot、openclaw、learn-claude-code、claw-code以及playwright。
agent-beta也是focus的项目，是打算从0开始新建一个，和agent-alpha这条“从skill-mcp-agent出发逐步简化”的路线不同。
期望改的目标：1 减少冗余代码 2 优化代码架构 3 提高配置灵活性和模块化 4 提升鲁棒性 5 每一个agent类，可以输入工作路径、自动识别agent人格md文档，便于多agent编排
