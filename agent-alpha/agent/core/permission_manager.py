"""Permission prompts for ask-once sandbox decisions."""

import json
from pathlib import Path
from typing import Dict, Any, Union


class PermissionManager:
    """Permission manager focused on one-time user approval prompts."""

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

    def ask_user(self, tool: str, args: Dict[str, Any], reason: str = "") -> Union[bool, Dict[str, str]]:
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
        if reason:
            print(f"原因: {reason}")
        print("━" * 70)
        print("[A] 允许一次")
        print("[N] 拒绝")
        print("[E] 追加指令后重试")
        print("━" * 70)

        while True:
            choice = input("选择: ").strip().upper()

            if choice == 'A':
                # 允许一次
                return True

            elif choice == 'N':
                # 拒绝
                print(f"❌ 已拒绝")
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

    def set_mode(self, mode: str):
        """保留模式接口以兼容现有管理入口。"""
        self.mode = mode
        print(f"✅ 权限模式已切换为: {mode}")


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
