"""
Event models for the in-process message bus.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict


@dataclass(slots=True)
class InboundMessage:
    source: str
    target: str
    kind: str
    content: str
    session_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass(slots=True)
class OutboundMessage:
    source: str
    target: str
    kind: str
    content: str
    session_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass(slots=True)
class CronTrigger:
    job_id: str
    content: str
    session_id: str
    target: str = "agent"
    source: str = "cron"
    kind: str = "cron"
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
