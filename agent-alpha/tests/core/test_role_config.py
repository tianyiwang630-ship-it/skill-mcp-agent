from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from agent.core.role_config import RoleConfig


def test_role_config_defaults_to_allow_all_tools():
    role = RoleConfig(name="default")

    assert role.enabled_tool_groups == []
    assert role.allowed_tools == []
    assert role.denied_tools == []


def test_role_config_tracks_explicit_tool_policy():
    role = RoleConfig(
        name="worker",
        enabled_tool_groups=["filesystem"],
        allowed_tools=["read", "write"],
        denied_tools=["bash"],
    )

    assert role.enabled_tool_groups == ["filesystem"]
    assert role.allowed_tools == ["read", "write"]
    assert role.denied_tools == ["bash"]
