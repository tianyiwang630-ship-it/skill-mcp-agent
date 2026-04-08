"""
Shared request/response types for the agent runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass(slots=True)
class RuntimeRequest:
    """Single runtime invocation payload."""

    content: str
    session_id: str = "runtime:local"
    source: str = "cli"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RuntimeResponse:
    """Single runtime invocation result."""

    content: str
    session_id: str
    source: str = "agent"
    metadata: Dict[str, Any] = field(default_factory=dict)
