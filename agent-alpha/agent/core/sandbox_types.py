from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


AccessAction = Literal["read", "write", "delete", "unknown"]
SandboxZone = Literal["workspace", "project", "outside", "unknown"]
SandboxDecision = Literal["allow", "ask", "deny"]
BashCategory = Literal[
    "read_only",
    "script_run",
    "package_install",
    "project_command",
    "path_mutation",
    "dangerous",
    "unknown",
]


@dataclass(frozen=True)
class SandboxCheckResult:
    decision: SandboxDecision
    action: AccessAction
    zone: SandboxZone
    reason: str
    guidance: str | None = None
