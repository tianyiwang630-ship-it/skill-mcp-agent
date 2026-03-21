1 我不懂代码，你和我交流要用我能理解的表达方式
2 执行前，必须和我讨论1-3轮，收束边界才能执行
3 后端接口使用fastapi库，遵循RESTFUL api的规范。
4 代码风格要简洁，如无必要毋增实体；代码要清晰，注重模块化和可扩展性。
5 中间产物放进temp文件夹
#背景知识
learnding proj是用来学习和借鉴的项目文件夹，文件夹内skill-mcp-agent是我之前的项目，nanobot是openclaw的轻量化实现，pi-mono是极简的agent框架，learn-claude-code是拆解claudecode实现的项目。
agent-alpha是现在focus的项目，希望能够简化skill-mcp-agent（agent-alpha内容就是skill-mcp-agent复制来的），并借鉴learnding proj中的pi-mono、nanobot以及learn-claude-code。
agent-beta也是focus的项目，是打算从0开始新建一个，和agent-alpha在目前的skill-mcp-agent基础上修改不同。
期望改的目标：1 减少冗余代码 2 优化代码架构 3 提高配置灵活性和模块化 4 提升鲁棒性 5每一个agent类，可以输入工作路径、自动识别agent人格md文档，便于多agent编排


