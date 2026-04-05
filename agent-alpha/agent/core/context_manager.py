"""
上下文管理器 - 负责 token 计数和历史压缩
"""

import json
import re
from typing import List, Dict, Any

import tiktoken

from agent.core.config import (
    MAX_CONTEXT_TOKENS,
    KEEP_RECENT_TURNS,
    COMPRESSION_THRESHOLD,
    COMPRESSION_INPUT_RATIO,
    TIKTOKEN_ENCODING,
    LLM_SUMMARY_MAX_TOKENS
)


class ContextManager:
    """上下文管理器 - 负责 token 计数和历史压缩"""

    def __init__(self, llm, tools: List[Dict], system_prompt: str,
                 max_context_tokens: int = MAX_CONTEXT_TOKENS,
                 keep_recent_turns: int = KEEP_RECENT_TURNS):
        """
        初始化上下文管理器

        Args:
            llm: LLMClient 实例（用于生成压缩摘要）
            tools: 工具定义列表
            system_prompt: 系统提示词
            max_context_tokens: 总上下文 token 限制
            keep_recent_turns: 压缩时保留最近 N 轮消息
        """
        self.llm = llm
        self.encoding = tiktoken.get_encoding(TIKTOKEN_ENCODING)

        self.max_context_tokens = max_context_tokens
        self.keep_recent_turns = keep_recent_turns
        self.compression_threshold = COMPRESSION_THRESHOLD

        # 计算固定成本
        self.system_tokens = self.count_tokens(system_prompt)
        self.tools_tokens = self._count_tools_tokens(tools)
        self.available_for_history = (
            self.max_context_tokens - self.system_tokens - self.tools_tokens
        )

        print(f"📊 上下文配置:")
        print(f"   - 总限制: {self.max_context_tokens:,} tokens")
        print(f"   - System: {self.system_tokens:,} tokens")
        print(f"   - Tools: {self.tools_tokens:,} tokens")
        print(f"   - History 可用: {self.available_for_history:,} tokens")

    # ============================================
    # 公开方法
    # ============================================

    def count_tokens(self, text: str) -> int:
        """
        计算文本的 token 数

        Args:
            text: 文本内容

        Returns:
            token 数量
        """
        if not text:
            return 0
        return len(self.encoding.encode(text))

    def count_history_tokens(self, history: List[Dict]) -> int:
        """
        计算 history 的 token 数

        Args:
            history: 对话历史

        Returns:
            history 的 token 数量
        """
        total = 0
        for msg in history:
            if msg.get("role") in ["user", "assistant", "tool"]:
                content = msg.get("content", "")
                if content:
                    total += self.count_tokens(content)

                # 如果 assistant 有 tool_calls，也计算
                if msg.get("tool_calls"):
                    tool_calls_json = json.dumps(msg["tool_calls"])
                    total += self.count_tokens(tool_calls_json)

        return total

    def should_compress(self, history: List[Dict]) -> bool:
        """
        检查是否需要压缩

        Args:
            history: 对话历史

        Returns:
            是否需要压缩
        """
        if len(history) <= self.keep_recent_turns:
            return False

        history_tokens = self.count_history_tokens(history)
        threshold = int(self.available_for_history * self.compression_threshold)
        should = history_tokens > threshold

        if should:
            print(f"\n⚠️  上下文即将超限: {history_tokens:,} / {threshold:,} tokens (阈值 {self.compression_threshold*100:.0f}%)")

        return should

    def compress_history(self, history: List[Dict]) -> List[Dict]:
        """
        压缩 history，返回新的 history 列表

        Args:
            history: 原始对话历史

        Returns:
            压缩后的新 history 列表
        """
        print("\n🗜️  开始压缩对话历史...")

        # 1. 分离旧对话和最近对话
        recent_history = history[-self.keep_recent_turns:]
        old_history = history[:-self.keep_recent_turns]

        if not old_history:
            print("⚠️  没有需要压缩的历史")
            return history

        old_tokens = sum(
            self.count_tokens(msg.get("content", ""))
            for msg in old_history
            if msg.get("content")
        )

        print(f"   - 压缩前: {len(old_history)} 条消息, {old_tokens:,} tokens")

        # 2. 调用 LLM 生成压缩摘要（JSON）
        try:
            summary_json = self._generate_summary(old_history)

            # 3. JSON → Markdown
            summary_md = self._json_to_markdown(summary_json)

            summary_tokens = self.count_tokens(summary_md)

            # 4. 重组 history
            new_history = [
                {
                    "role": "user",
                    "content": summary_md
                }
            ] + recent_history

            compression_ratio = (1 - summary_tokens / old_tokens) * 100 if old_tokens > 0 else 0

            print(f"   - 压缩后: 1 条摘要, {summary_tokens:,} tokens")
            print(f"   - 压缩率: {compression_ratio:.1f}%")
            print(f"✅ 压缩完成，保留最近 {self.keep_recent_turns} 轮\n")

            return new_history

        except Exception as e:
            print(f"❌ 压缩失败: {e}，回退到机械截断")
            import traceback
            traceback.print_exc()
            # 不返回原始 history（会导致死循环），改为机械截断
            return history[-self.keep_recent_turns * 2:]

    # ============================================
    # 私有方法
    # ============================================

    def _count_tools_tokens(self, tools: List[Dict]) -> int:
        """
        计算 tools 的 token 数

        Args:
            tools: 工具定义列表

        Returns:
            tools 的 token 数量
        """
        tools_json = json.dumps(tools)
        return self.count_tokens(tools_json)

    def _generate_summary(self, old_history: List[Dict]) -> dict:
        """
        调用 LLM 生成压缩摘要

        Args:
            old_history: 需要压缩的历史消息

        Returns:
            压缩后的 JSON 摘要
        """
        # 构建摘要提示词
        summary_prompt = """# 任务：将对话历史压缩为结构化摘要

输出 JSON 格式，包含 6 个字段：

## 1. task_timeline（因果链步骤）
```json
[{
  "step": 1,
  "user_request": "用户请求简述",
  "action": "执行的操作",
  "result": "成功/失败",
  "key_output": "关键输出（文件路径/数据）",
  "note": "备注"
}]
```
- 只记录推进任务的关键步骤
- 保持因果链完整

## 2. skill_deltas（关键工具调用）
```json
[{
  "tool": "工具名",
  "action": "具体操作",
  "impact": "影响",
  "timestamp_relative": "第几轮"
}]
```
- ✅ 保留：write/edit/bash(非查询)/创建修改删除
- ❌ 废弃：ls/pwd/cat/read/git status

## 3. important_files（文件清单）
```json
[{
  "path": "/完整/路径/file.py",
  "tool": "write/edit/bash",
  "created_by": "对应步骤",
  "status": "created/modified/deleted"
}]
```
- 必须完整路径
- 省略临时文件

## 4. current_state（当前状态）
```json
{
  "just_finished": "刚完成什么",
  "interrupted_at": "被打断在做什么",
  "next_step": "下一步做什么",
  "waiting_for": "等待用户什么"
}
```

## 5. error_memory（错误记忆）
```json
[{
  "error": "错误信息",
  "context": "什么操作导致",
  "correction": "如何纠正",
  "success": "纠正后结果",
  "lesson": "教训（具体规则）"
}]
```
- 只记录有价值的错误

## 6. critical_user_intents（关键意图）
```json
[{
  "turn": 3,
  "intent": "核心意图",
  "reason": "为什么重要"
}]
```
- 只保留需求变更、新增要求、特定偏好等转折点

---

## 压缩原则
1. 去重合并：相同操作合并为一条
2. 保持因果：删除无因果的中间步骤
3. 具体化：必须有具体文件名/路径/值
4. 面向恢复：确保能继续对话

请基于以下对话历史生成摘要，直接输出 JSON，不要有任何其他文字：

"""

        # 添加历史记录（截断到 max_context_tokens 的 90% 防止 LLM 返空）
        history_text = json.dumps(old_history, ensure_ascii=False, indent=2)
        max_summary_input = int(self.max_context_tokens * COMPRESSION_INPUT_RATIO)
        if self.count_tokens(history_text) > max_summary_input:
            kept = []
            running = 0
            for msg in reversed(old_history):
                t = self.count_tokens(json.dumps(msg, ensure_ascii=False))
                if running + t > max_summary_input:
                    break
                kept.append(msg)
                running += t
            kept.reverse()
            history_text = json.dumps(kept, ensure_ascii=False, indent=2)
            print(f"   - 压缩输入已截断: 保留 {len(kept)}/{len(old_history)} 条消息")

        full_prompt = summary_prompt + "\n" + history_text

        # 调用 LLM
        print("   - 正在生成摘要...")
        response = self.llm.generate(full_prompt, max_tokens=LLM_SUMMARY_MAX_TOKENS)

        # 空响应检查
        if not response or not response.strip():
            raise ValueError("LLM 返回空响应，无法生成摘要")

        # 解析 JSON
        try:
            # 尝试直接解析
            summary_json = json.loads(response)
        except json.JSONDecodeError:
            # 如果包含 markdown 代码块，提取 JSON
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_match:
                summary_json = json.loads(json_match.group(1))
            else:
                raise ValueError(f"无法解析 JSON 摘要: {response[:200]}")

        return summary_json

    def _json_to_markdown(self, summary_json: dict) -> str:
        """
        将压缩 JSON 转为 Markdown

        Args:
            summary_json: 压缩后的 JSON 摘要

        Returns:
            Markdown 格式的摘要
        """
        lines = []
        lines.append("# 📋 历史对话摘要")
        lines.append("")

        # 1. 任务时间线
        if summary_json.get("task_timeline"):
            lines.append("## 🎯 任务时间线")
            for item in summary_json["task_timeline"]:
                lines.append(f"{item['step']}. **用户请求**：{item['user_request']}")
                lines.append(f"   **操作**：{item['action']}")
                lines.append(f"   **结果**：{item['result']}")
                if item.get('key_output'):
                    lines.append(f"   **输出**：{item['key_output']}")
                if item.get('note'):
                    lines.append(f"   **备注**：{item['note']}")
                lines.append("")

        # 2. 关键工具调用
        if summary_json.get("skill_deltas"):
            lines.append("## 🔧 关键工具调用")
            for item in summary_json["skill_deltas"]:
                lines.append(f"- `{item['tool']}` → {item['action']} → {item['impact']}")
            lines.append("")

        # 3. 重要文件
        if summary_json.get("important_files"):
            lines.append("## 📁 重要文件")
            for item in summary_json["important_files"]:
                lines.append(f"- `{item['path']}` ({item['status']})")
            lines.append("")

        # 4. 当前状态
        if summary_json.get("current_state"):
            state = summary_json["current_state"]
            lines.append("## 📍 当前状态")
            if state.get("just_finished"):
                lines.append(f"- ✅ 刚完成：{state['just_finished']}")
            if state.get("interrupted_at"):
                lines.append(f"- ⏸️  被打断：{state['interrupted_at']}")
            if state.get("next_step"):
                lines.append(f"- 📋 下一步：{state['next_step']}")
            if state.get("waiting_for"):
                lines.append(f"- ⏳ 等待：{state['waiting_for']}")
            lines.append("")

        # 5. 错误记忆
        if summary_json.get("error_memory"):
            lines.append("## ⚠️ 错误记忆")
            for item in summary_json["error_memory"]:
                lines.append(f"- **错误**：{item['error']}")
                lines.append(f"  **纠正**：{item['correction']}")
                lines.append(f"  **教训**：{item['lesson']}")
                lines.append("")

        # 6. 关键用户意图
        if summary_json.get("critical_user_intents"):
            lines.append("## 💡 关键用户意图")
            for item in summary_json["critical_user_intents"]:
                lines.append(f"- (轮{item['turn']}) {item['intent']}")
            lines.append("")

        return "\n".join(lines)
