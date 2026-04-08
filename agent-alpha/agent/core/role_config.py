"""
Role-scoped runtime configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class RoleConfig:
    """Capability policy for a single agent runtime."""

    name: str = "default"
    enabled_tool_groups: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)
    denied_tools: list[str] = field(default_factory=list)
