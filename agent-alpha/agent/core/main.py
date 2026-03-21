"""
Agent 主编排 - 完整的对话式 Agent

功能：
- 自动加载所有工具（MCP + Skills + 内置）
- 多轮对话
- 工具调用
- 上下文管理（JSON 格式）
"""

# ============================================
# 路径处理 - 确保可以从任何位置运行
# ============================================
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# ============================================
# 导入模块
# ============================================
import json
import time
import threading
from typing import Any, List, Dict

try:
    import msvcrt  # Windows 按键检测
    HAS_MSVCRT = True
except ImportError:
    HAS_MSVCRT = False

from agent.core.llm import LLMClient
from agent.core.tool_loader import ToolLoader
from agent.core.context_manager import ContextManager
from agent.core.config import MAX_CONTEXT_TOKENS, KEEP_RECENT_TURNS, MAX_TOOL_RESULT_CHARS


class Agent:
    """完整的对话式 Agent"""

    def __init__(self, max_turns: int = 5000, workspace_root: str = None, task_id: str = None):
        """
        初始化 Agent

        Args:
            max_turns: 最大对话轮次
            workspace_root: 工作空间根目录（默认使用项目根目录）
            task_id: 任务 ID（可选，用于多 agent 场景下的任务隔离）
        """
        # ========== 路径配置 ==========
        # 如果没有指定 workspace_root，使用项目根目录
        if workspace_root is None:
            self.workspace_root = project_root
        else:
            self.workspace_root = Path(workspace_root).resolve()

        self.task_id = task_id

        # ========== 会话配置（需在路径计算前生成） ==========
        from datetime import datetime
        self.session_id = self._generate_session_id()
        self.session_start_time = datetime.now()

        # 计算输入输出目录的绝对路径
        self.input_dir = (self.workspace_root / "input files").resolve()
        self.output_dir = (self.workspace_root / "output files").resolve()
        self.temp_dir = (self.workspace_root / "temp" / self.session_id).resolve()
        self.logs_dir = (self.workspace_root / "workspace" / "logs").resolve()

        # 创建目录（如果不存在）
        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        # 初始化组件
        self.llm = LLMClient()
        self.tool_loader = ToolLoader()
        self.max_turns = max_turns

        # 对话历史（JSON 格式）
        self.history: List[Dict[str, Any]] = []

        # 中断信号（双 ESC 触发）
        self._interrupted = threading.Event()

        # 加载所有工具
        print("🤖 初始化 Agent...")
        self.tools = self.tool_loader.load_all()

        # 注入 temp_dir 到需要的工具
        fetch = self.tool_loader.tool_instances.get("fetch")
        if fetch:
            fetch.temp_dir = self.temp_dir

        # 显示路径配置
        print(f"\n📂 工作空间配置:")
        print(f"   - 根目录: {self.workspace_root}")
        print(f"   - 输入目录: {self.input_dir}")
        print(f"   - 输出目录: {self.output_dir}")
        print(f"   - 临时目录: {self.temp_dir}")
        print(f"   - 日志目录: {self.logs_dir}")
        print(f"   - 会话 ID: {self.session_id}")
        if self.task_id:
            print(f"   - 任务 ID: {self.task_id}")

        # 系统提示（动态生成，包含绝对路径）
        self.system_prompt = self._build_system_prompt()

        # ========== 上下文管理器 ==========
        self.context_manager = ContextManager(
            llm=self.llm,
            tools=self.tools,
            system_prompt=self.system_prompt,
            max_context_tokens=MAX_CONTEXT_TOKENS,
            keep_recent_turns=KEEP_RECENT_TURNS
        )

    def _generate_session_id(self) -> str:
        """
        生成唯一的会话ID（短格式）

        Returns:
            6位字符的会话ID（例如：a1b2c3）
        """
        import uuid
        # 生成UUID并取前6位
        return uuid.uuid4().hex[:6]

    def _build_system_prompt(self) -> str:
        """
        动态生成 system prompt，包含明确的路径信息

        Returns:
            完整的 system prompt
        """
        task_info = f"当前任务 ID: {self.task_id}" if self.task_id else "单一任务模式"

        prompt = f"""你是一个智能助手，可以使用工具完成任务。现在是2026年。

<workspace_info>
  {task_info}
  工作空间根目录: {self.workspace_root}

  输入文件目录: {self.input_dir}
  输出文件目录: {self.output_dir}
  临时文件目录: {self.temp_dir}
</workspace_info>

<path_rules>
1. **读取文件**: 除非特殊说明，用户上传的文件位于 {self.input_dir}
2. **写入文件**: 除非特殊说明，生成的结果文件应保存到 {self.output_dir}
3. **临时文件**: 中间过程文件可保存到 {self.temp_dir}
4. **使用绝对路径**: 为了避免混淆，请始终使用上述绝对路径进行文件操作
</path_rules>

<large_file_strategy>
当需要创建大文件（超过5000字或15KB）时，必须使用分块写入策略：

1. 第一块：使用 write 工具创建文件并写入第一部分内容
2. 后续块：使用 append 工具逐块追加剩余内容
3. 每块内容控制在5000字以内，在章节边界处分块
4. 写入前告知用户正在分块写入

示例流程：
  write(file_path, "# 标题\n## 第一章\n...")   → 创建文件
  append(file_path, "\n## 第二章\n...")          → 追加
  append(file_path, "\n## 第三章\n...")          → 追加

对于已存在的大文件，优先使用 edit 工具进行增量修改，避免重写整个文件。
如果创建文件文件过大，输出被截断，json解析错误，则可以先输出第一部分，然后通过
</large_file_strategy>
"""

        return prompt

    def run(self, user_input: str) -> str:
        """
        运行 Agent（单轮对话）

        Args:
            user_input: 用户输入

        Returns:
            Agent 响应
        """
        # 检查是否需要压缩上下文
        if self.context_manager.should_compress(self.history):
            self.history = self.context_manager.compress_history(self.history)

        # 添加用户消息到历史
        self.history.append({
            "role": "user",
            "content": user_input
        })

        # 多轮工具调用（支持双 ESC 中断）
        self._interrupted.clear()
        esc_thread = self._start_esc_listener()

        try:
            for turn in range(self.max_turns):
                if self._interrupted.is_set():
                    break

                messages = self._build_messages()
                message = self._call_llm_interruptible(messages)

                if message is None:  # 被中断
                    break

                if message.tool_calls:
                    self._handle_tool_calls(message)
                    if self._interrupted.is_set():
                        break
                    continue
                else:
                    # 没有工具调用，返回最终响应
                    self.history.append({
                        "role": "assistant",
                        "content": message.content
                    })
                    return message.content

            # 被中断或达到最大轮次
            if self._interrupted.is_set():
                return "[用户中断] 已停止当前任务。"
            return "抱歉，任务太复杂，已达到最大处理轮次。"
        finally:
            self._interrupted.set()  # 停止 ESC 监听线程

    def _call_llm(self, messages: List[Dict]) -> Any:
        """
        调用 LLM 并处理调试日志

        Args:
            messages: 消息列表

        Returns:
            LLM 响应的 message 对象
        """
        response = self.llm.generate_with_tools(
            messages=messages,
            tools=self.tools
        )

        message = response.choices[0].message

        # 调试模式：保存响应
        if hasattr(message, 'tool_calls') and message.tool_calls:
            import os
            debug_mode = os.environ.get('DEBUG_AGENT', '0') == '1'
            if debug_mode:
                debug_file = Path("workspace/temp/last_llm_response.json")
                debug_file.parent.mkdir(parents=True, exist_ok=True)
                debug_data = {
                    "content": message.content,
                    "tool_calls": [
                        {
                            "name": tc.function.name,
                            "arguments_raw": tc.function.arguments
                        }
                        for tc in message.tool_calls
                    ]
                }
                debug_file.write_text(json.dumps(debug_data, ensure_ascii=False, indent=2), encoding='utf-8')

        return message

    # ============================================
    # 中断机制
    # ============================================

    def _start_esc_listener(self):
        """后台线程：监听双 ESC 中断（1 秒内按两次 ESC 触发）"""
        if not HAS_MSVCRT:
            return None  # 非 Windows 环境不启动

        self._interrupted.clear()
        last_esc = [0.0]

        def listener():
            while not self._interrupted.is_set():
                if msvcrt.kbhit():
                    key = msvcrt.getch()
                    if key == b'\x1b':  # ESC
                        now = time.time()
                        if now - last_esc[0] < 1.0:
                            self._interrupted.set()
                            print("\n\n⏸️  检测到双 ESC，正在中断...")
                            return
                        last_esc[0] = now
                time.sleep(0.05)

        t = threading.Thread(target=listener, daemon=True)
        t.start()
        return t

    def _call_llm_interruptible(self, messages):
        """在子线程中调用 LLM，主线程可通过 _interrupted 中断等待"""
        result: list = [None]
        error: list = [None]

        def call():
            try:
                result[0] = self._call_llm(messages)
            except Exception as e:
                error[0] = e

        t = threading.Thread(target=call)
        t.start()

        while t.is_alive():
            t.join(timeout=0.1)
            if self._interrupted.is_set():
                return None  # 中断，API 调用在后台完成但结果被丢弃

        if error[0]:
            raise error[0]
        return result[0]

    def _handle_tool_calls(self, message) -> None:
        """
        处理工具调用

        Args:
            message: LLM 响应的 message 对象
        """
        # 添加 assistant 消息（带工具调用）
        self.history.append({
            "role": "assistant",
            "content": message.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in message.tool_calls
            ]
        })

        # 执行所有工具
        for tool_call in message.tool_calls:
            # 中断检查：为未执行的 tool_call 补占位结果
            if self._interrupted.is_set():
                self.history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": "[用户中断] 此工具调用未执行"
                })
                continue

            result = self._execute_single_tool(tool_call)

            # 检测重试请求（用户添加额外指令）
            if isinstance(result, dict) and "retry_with_context" in result:
                extra_instruction = result["retry_with_context"]

                print(f"💬 用户添加了额外指令: {extra_instruction}")
                print(f"🔄 移除当前工具调用，让 AI 重新思考...\n")

                # 移除刚添加的 assistant 消息（包含 tool_calls）
                if self.history and self.history[-1]["role"] == "assistant":
                    self.history.pop()

                # 将额外指令作为用户消息添加到历史
                self.history.append({
                    "role": "user",
                    "content": f"[补充说明] {extra_instruction}"
                })

                # 跳出工具执行循环，让 LLM 重新思考
                break

            # 转换结果为字符串
            if isinstance(result, dict):
                result_str = json.dumps(result, ensure_ascii=False)
            else:
                result_str = str(result)

            # 清理 ANSI 转义码（部分 LLM API 不接受控制字符）
            import re
            result_str = re.sub(r'\x1b\[[0-9;]*m', '', result_str)

            # 全局截断：防止单个工具结果撑爆上下文
            if len(result_str) > MAX_TOOL_RESULT_CHARS:
                result_str = result_str[:MAX_TOOL_RESULT_CHARS] + f"\n\n... (已截断，原始 {len(result_str)} 字符)"

            print(f"   结果: {result_str[:100]}...")

            # 添加工具结果到历史
            self.history.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result_str
            })

    def _execute_single_tool(self, tool_call) -> Any:
        """
        解析参数并执行单个工具

        Args:
            tool_call: 工具调用对象

        Returns:
            工具执行结果
        """
        tool_name = tool_call.function.name
        raw_arguments = tool_call.function.arguments

        print(f"\n🔧 调用工具: {tool_name}")
        print(f"   原始参数: {raw_arguments[:200] if len(raw_arguments) > 200 else raw_arguments}")

        # JSON 解析 + 错误处理
        try:
            arguments = json.loads(raw_arguments)
            print(f"   解析成功")
        except json.JSONDecodeError as e:
            print(f"   ❌ JSON 解析错误: {e}")
            print(f"   原始内容: {raw_arguments}")
            try:
                fixed_args = raw_arguments.replace("'", '"')
                arguments = json.loads(fixed_args)
                print(f"   ✅ 修复成功，使用修复后的参数")
            except:
                print(f"   ⚠️  无法修复，使用空参数")
                arguments = {}

        return self.tool_loader.execute_tool(tool_name, arguments)

    def _build_messages(self) -> List[Dict[str, Any]]:
        """
        构建发送给 LLM 的消息列表

        Returns:
            消息列表
        """
        messages = [
            {"role": "system", "content": self.system_prompt}
        ]

        # 添加历史消息
        messages.extend(self.history)

        return messages

    def get_context_json(self) -> str:
        """
        获取完整上下文（JSON 格式）

        Returns:
            JSON 字符串
        """
        context = {
            "system_prompt": self.system_prompt,
            "available_tools": len(self.tools),
            "history": self.history
        }

        return json.dumps(context, ensure_ascii=False, indent=2)

    def save_context(self, filepath: str):
        """保存上下文到文件"""
        Path(filepath).write_text(self.get_context_json(), encoding='utf-8')
        print(f"💾 上下文已保存: {filepath}")

    def reset(self):
        """重置对话历史"""
        self.history = []
        print("🔄 对话已重置")

    def save_session_log(self):
        """
        保存会话日志到 workspace/logs/ 目录（JSON格式）

        日志文件命名格式：YYYY-MM-DD_HH-MM-SS_session_{session_id}.json
        """
        from datetime import datetime

        # 如果没有对话历史，跳过保存
        if not self.history:
            print("📝 无对话历史，跳过保存")
            return

        # 生成文件名
        session_end_time = datetime.now()
        timestamp = self.session_start_time.strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{timestamp}_session_{self.session_id}.json"
        filepath = self.logs_dir / filename

        # 构建日志数据
        log_data = {
            "session_id": self.session_id,
            "start_time": self.session_start_time.isoformat(),
            "end_time": session_end_time.isoformat(),
            "duration_seconds": (session_end_time - self.session_start_time).total_seconds(),
            "total_turns": len([msg for msg in self.history if msg["role"] == "user"]),
            "history": self.history
        }

        # 保存到文件
        try:
            filepath.write_text(
                json.dumps(log_data, ensure_ascii=False, indent=2),
                encoding='utf-8'
            )
            print(f"💾 会话日志已保存: {filepath}")
            self._append_session_index(filepath)
        except Exception as e:
            print(f"❌ 保存会话日志失败: {e}")

    def _append_session_index(self, log_filepath: Path):
        """追加会话记录到 temp/sessions.md"""
        try:
            index_file = self.workspace_root / "temp" / "sessions.md"
            session_temp = self.workspace_root / "temp" / self.session_id

            # 统计信息
            user_turns = len([m for m in self.history if m["role"] == "user"])
            first_msg = next((m["content"][:100] for m in self.history if m["role"] == "user"), "")
            first_msg = first_msg.replace("\n", " ").replace("|", "/")
            has_temp = session_temp.exists() and any(session_temp.iterdir())

            # 如果文件不存在，写表头
            if not index_file.exists():
                header = "# 会话索引\n\n"
                header += "| 会话ID | 时间 | 轮次 | 临时文件 | 日志路径 | 首条消息 |\n"
                header += "|--------|------|------|----------|----------|----------|\n"
                index_file.write_text(header, encoding="utf-8")

            # 追加一行
            time_str = self.session_start_time.strftime("%m-%d %H:%M")
            temp_str = f"temp/{self.session_id}/" if has_temp else "-"
            log_str = str(log_filepath.relative_to(self.workspace_root))
            line = f"| {self.session_id} | {time_str} | {user_turns} | {temp_str} | {log_str} | {first_msg} |\n"

            with open(index_file, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception as e:
            print(f"⚠️ 更新会话索引失败: {e}")


# ============================================
# 使用示例
# ============================================

if __name__ == "__main__":
    import sys

    # 默认交互模式
    print("=" * 70)
    print("🤖 Agent 交互模式")
    print("=" * 70)

    agent = Agent()

    print("\n💡 命令:")
    print("   - 直接输入任务，Agent 会使用工具完成")
    print("   - 'quit' / 'exit' - 退出（自动保存日志）")
    print("   - 'reset' - 重置对话")
    print("   - 'context' - 查看上下文")
    print("   - 'save' - 保存上下文到文件")
    print("   - 'save-log' - 手动保存会话日志")
    print("   - '/admin' - 权限模式设置")
    print("   - 双击 ESC - 中断 AI 思考/工具执行\n")

    while True:
        try:
            # 用户输入
            user_input = input("👤 你: ").strip()

            if not user_input:
                continue

            # 退出命令
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\n👋 再见！")
                agent.save_session_log()
                break

            # 重置对话
            if user_input.lower() == 'reset':
                agent.reset()
                continue

            # 查看上下文
            if user_input.lower() == 'context':
                print("\n" + "=" * 70)
                print(agent.get_context_json())
                print("=" * 70 + "\n")
                continue

            # 保存上下文
            if user_input.lower() == 'save':
                from pathlib import Path
                save_path = Path("workspace/temp/agent_context.json")
                save_path.parent.mkdir(parents=True, exist_ok=True)
                agent.save_context(str(save_path))
                continue

            # 保存会话日志
            if user_input.lower() == 'save-log':
                agent.save_session_log()
                continue

            # 权限管理
            if user_input.lower() == '/admin':
                print("\n" + "=" * 70)
                print("🔐 权限模式设置")
                print("=" * 70)

                # 显示当前模式
                current_mode = agent.tool_loader.permission_manager.mode
                print(f"\n当前模式: {current_mode}")

                print("\n请选择权限模式:")
                print("  [1] ask - 编辑前询问（查看操作自动允许）")
                print("  [2] auto - 自动编辑（所有操作自动允许）")
                print("  [0] 取消")
                print("=" * 70)

                choice = input("选择 (1/2/0): ").strip()

                if choice == '1':
                    agent.tool_loader.permission_manager.set_mode("ask")
                elif choice == '2':
                    agent.tool_loader.permission_manager.set_mode("auto")
                elif choice == '0':
                    print("❌ 已取消")
                else:
                    print("⚠️  无效选择")

                print()
                continue

            # 运行 Agent
            print()
            response = agent.run(user_input)
            print(f"\n🤖 Agent: {response}\n")

        except KeyboardInterrupt:
            print("\n\n👋 检测到 Ctrl+C，退出...")
            agent.save_session_log()
            # 显式关闭 MCP 连接和子进程，避免 threading._shutdown 阻塞
            mcp_mgr = agent.tool_loader.tool_executors.get('_mcp_manager')
            if mcp_mgr:
                try:
                    mcp_mgr.close_all()
                except Exception:
                    pass
            break
        except Exception as e:
            print(f"\n❌ 错误: {e}")
            import traceback
            traceback.print_exc()
            print()
