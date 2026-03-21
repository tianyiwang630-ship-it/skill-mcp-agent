"""
权限管理器 - 控制工具使用权限
"""

import json
import fnmatch
from pathlib import Path
from typing import Dict, Any, Set, Literal, Union


class PermissionManager:
    """权限管理器 - 管理工具使用权限"""

    def __init__(self, config_path: Path = None):
        """
        初始化权限管理器

        Args:
            config_path: 配置文件路径，默认为 agent/core/permissions.json
        """
        if config_path is None:
            config_path = Path(__file__).parent / "permissions.json"

        self.config_path = config_path
        self.config = self._load_config()
        self.mode = self.config.get("mode", "default")

        # 会话级缓存（内存中）
        self.session_allowed: Set[str] = set()
        self.session_denied: Set[str] = set()

    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  权限配置加载失败: {e}")
            # 返回默认配置
            return {
                "mode": "default",
                "permissions": {
                    "deny": [],
                    "allow": [],
                    "ask": []
                }
            }

    def check_permission(
        self,
        tool: str,
        args: Dict[str, Any],
        mode: str = None
    ) -> Literal["allow", "deny", "ask"]:
        """
        检查权限

        Args:
            tool: 工具名称
            args: 工具参数
            mode: 权限模式（可选，默认使用配置文件的 mode）

        Returns:
            "allow" - 允许
            "deny" - 拒绝
            "ask" - 询问用户
        """
        if mode is None:
            mode = self.mode

        # 生成签名（用于会话缓存）
        signature = self._get_signature(tool, args)

        # 1. 检查会话缓存
        if signature in self.session_denied:
            return "deny"
        if signature in self.session_allowed:
            return "allow"

        # 2. 检查 deny 规则（最高优先级）
        permissions = self.config.get("permissions", {})
        for pattern in permissions.get("deny", []):
            if self._match_rule(pattern, tool, args):
                return "deny"

        # 3. auto 模式：所有非 deny 的操作都允许
        if mode == "auto":
            return "allow"

        # 4. 检查 allow 规则
        for pattern in permissions.get("allow", []):
            if self._match_rule(pattern, tool, args):
                return "allow"

        # 5. 检查 ask 规则
        for pattern in permissions.get("ask", []):
            if self._match_rule(pattern, tool, args):
                return "ask"

        # 6. 默认行为（根据 mode）
        return self._get_default_permission(tool, mode)

    def _get_signature(self, tool: str, args: Dict[str, Any]) -> str:
        """
        生成工具调用的唯一签名（用于会话缓存）

        Args:
            tool: 工具名称
            args: 工具参数

        Returns:
            签名字符串
        """
        if tool == "bash":
            return f"bash:{args.get('command', '')}"
        elif tool in ["read", "write", "edit"]:
            return f"{tool}:{args.get('file_path', '')}"
        elif tool in ["glob", "grep"]:
            return f"{tool}:{args.get('pattern', '')}"
        elif tool.startswith("mcp__"):
            # MCP 工具：使用工具名作为签名
            # 一次授权后，会话期间所有对该工具的调用都生效
            return tool
        elif tool == "fetch":
            # fetch 是只读工具，用工具名作为签名
            # 一次授权后，会话期间所有 URL 的 fetch 调用都生效
            return tool
        else:
            # 其他工具使用 JSON 序列化
            return f"{tool}:{json.dumps(args, sort_keys=True)}"

    def _match_rule(self, pattern: str, tool: str, args: Dict[str, Any]) -> bool:
        """
        匹配规则（支持 glob 模式）

        规则格式:
            - "tool" - 匹配整个工具
            - "tool:pattern" - 匹配工具 + 参数模式

        Args:
            pattern: 规则模式
            tool: 工具名称
            args: 工具参数

        Returns:
            是否匹配
        """
        if ':' not in pattern:
            # 简单工具匹配
            return fnmatch.fnmatch(tool, pattern)

        # 解析规则: tool:pattern
        rule_tool, rule_pattern = pattern.split(':', 1)

        # 工具名不匹配
        if not fnmatch.fnmatch(tool, rule_tool):
            return False

        # 获取实际值
        actual_value = self._get_value_for_tool(tool, args)

        # Glob 模式匹配
        return fnmatch.fnmatch(actual_value, rule_pattern)

    def _get_value_for_tool(self, tool: str, args: Dict[str, Any]) -> str:
        """
        获取工具的实际值（用于匹配）

        Args:
            tool: 工具名称
            args: 工具参数

        Returns:
            实际值字符串
        """
        if tool == "bash":
            return args.get('command', '')
        elif tool in ["read", "write", "edit"]:
            return args.get('file_path', '')
        elif tool in ["glob", "grep"]:
            return args.get('pattern', '')
        elif tool == "fetch":
            return args.get('url', '')
        else:
            # 默认返回 JSON
            return json.dumps(args, sort_keys=True)

    def _get_default_permission(
        self,
        tool: str,
        mode: str
    ) -> Literal["allow", "deny", "ask"]:
        """
        获取默认权限（当规则未匹配时）

        Args:
            tool: 工具名称
            mode: 权限模式

        Returns:
            默认权限
        """
        # ask 模式：查看操作允许，编辑操作询问
        if mode == "ask":
            if tool in ["read", "glob", "grep", "fetch"]:
                return "allow"
            elif tool in ["write", "edit"]:
                return "ask"
            elif tool == "bash":
                # bash 命令默认允许（危险命令已在 deny 规则中）
                return "allow"
            else:
                return "ask"

        # auto 模式：所有操作自动允许（除了 deny 规则）
        elif mode == "auto":
            return "allow"

        # 兼容旧模式名称
        elif mode == "default":
            return self._get_default_permission(tool, "ask")
        elif mode == "permissive":
            return self._get_default_permission(tool, "auto")

        else:
            # 未知模式，默认 ask
            return self._get_default_permission(tool, "ask")

    def ask_user(self, tool: str, args: Dict[str, Any]) -> Union[bool, Dict[str, str]]:
        """
        询问用户是否允许

        Args:
            tool: 工具名称
            args: 工具参数

        Returns:
            True - 允许
            False - 拒绝
            Dict - 重试请求，包含额外指令
        """
        # 获取风险等级
        risk_level = self._get_risk_level(tool, args)
        risk_emoji = self._get_risk_emoji(risk_level)

        # 格式化显示
        print("\n" + "━" * 70)
        print("⚠️  权限请求")
        print("━" * 70)
        print(f"工具: {tool}")

        # 显示详细信息
        if tool == "bash":
            print(f"命令: {args.get('command', '')}")
        elif tool in ["read", "write", "edit"]:
            print(f"文件: {args.get('file_path', '')}")
        elif tool in ["glob", "grep"]:
            print(f"模式: {args.get('pattern', '')}")
        elif tool == "fetch":
            print(f"URL: {args.get('url', '')}")
        else:
            print(f"参数: {json.dumps(args, ensure_ascii=False, indent=2)}")

        print(f"风险: {risk_emoji} {risk_level}")
        print("━" * 70)
        print("[A] 允许一次")
        print("[Y] 本次会话总是允许")
        print("[N] 拒绝")
        print("[D] 本次会话总是拒绝")
        print("[E] 追加指令后重试")
        print("[S] 切换到自动模式（后续全部自动允许）")
        print("━" * 70)

        while True:
            choice = input("选择: ").strip().upper()

            if choice == 'A':
                # 允许一次
                return True

            elif choice == 'Y':
                # 本次会话总是允许
                signature = self._get_signature(tool, args)
                self.session_allowed.add(signature)
                print(f"✅ 已添加到会话白名单")
                return True

            elif choice == 'N':
                # 拒绝
                print(f"❌ 已拒绝")
                return False

            elif choice == 'D':
                # 本次会话总是拒绝
                signature = self._get_signature(tool, args)
                self.session_denied.add(signature)
                print(f"🚫 已添加到会话黑名单")
                return False

            elif choice == 'E':
                # 追加指令后重试
                print("\n💬 请输入额外指令（帮助 AI 更好地理解您的需求）:")
                extra_instruction = input(">>> ").strip()

                if not extra_instruction:
                    print("⚠️  未输入指令，请重新选择")
                    continue

                print(f"✅ 已添加额外指令，将重新处理请求\n")
                return {
                    "retry_with_context": extra_instruction
                }

            elif choice == 'S':
                # 切换到自动模式
                self.mode = "auto"
                print("⚡ 已切换到自动模式，后续操作将自动批准")
                return True

            else:
                print("⚠️  无效选择，请重新输入")

    def _get_risk_level(self, tool: str, args: Dict[str, Any]) -> str:
        """
        获取风险等级

        Args:
            tool: 工具名称
            args: 工具参数

        Returns:
            "low" | "medium" | "high"
        """
        risk_levels = self.config.get("risk_levels", {})

        # 工具固定风险
        tool_risk = risk_levels.get(tool)
        if tool_risk and tool_risk != "auto":
            return tool_risk

        # Bash 命令动态判断
        if tool == "bash":
            command = args.get("command", "")
            keywords = self.config.get("bash_risk_keywords", {})

            # 检查高危关键词
            for keyword in keywords.get("high", []):
                if keyword in command:
                    return "high"

            # 检查中危关键词
            for keyword in keywords.get("medium", []):
                if keyword in command:
                    return "medium"

            return "low"

        # 默认中等
        return "medium"

    def _get_risk_emoji(self, level: str) -> str:
        """获取风险等级对应的 emoji"""
        return {
            "low": "🟢 低",
            "medium": "🟡 中等",
            "high": "🔴 高"
        }.get(level, "🟡 中等")

    def set_mode(self, mode: Literal["ask", "auto"]):
        """
        设置权限模式

        Args:
            mode: 权限模式
                - "ask": 编辑前询问（查看自动允许）
                - "auto": 自动编辑（所有操作自动允许）
        """
        if mode not in ["ask", "auto"]:
            raise ValueError(f"Invalid mode: {mode}. Must be 'ask' or 'auto'")

        self.mode = mode

        # 显示模式说明
        mode_desc = {
            "ask": "编辑前询问（查看自动允许）",
            "auto": "自动编辑（所有操作自动允许）"
        }
        print(f"✅ 权限模式已切换为: {mode} - {mode_desc[mode]}")

    def clear_session_cache(self):
        """清除会话缓存"""
        self.session_allowed.clear()
        self.session_denied.clear()
        print("✅ 会话缓存已清除")


# ============================================
# 使用示例
# ============================================

if __name__ == "__main__":
    print("=" * 70)
    print("Permission Manager 测试")
    print("=" * 70)

    # 创建管理器
    pm = PermissionManager()

    # 测试用例
    test_cases = [
        ("read", {"file_path": "./src/test.py"}),
        ("bash", {"command": "git status"}),
        ("bash", {"command": "rm -rf /"}),
        ("write", {"file_path": "./test.txt", "content": "hello"}),
        ("bash", {"command": "git push origin main"}),
    ]

    for tool, args in test_cases:
        print(f"\n{'='*70}")
        print(f"测试: {tool} - {args}")
        print(f"{'='*70}")

        permission = pm.check_permission(tool, args)
        print(f"权限检查结果: {permission}")

        if permission == "ask":
            allowed = pm.ask_user(tool, args)
            print(f"用户决定: {'允许' if allowed else '拒绝'}")

    print(f"\n{'='*70}")
    print("测试完成")
    print(f"{'='*70}")
