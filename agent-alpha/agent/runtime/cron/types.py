"""
Cron job data types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass(slots=True)
class CronJob:
    job_id: str
    name: str
    content: str
    session_id: str
    target: str = "agent"
    metadata: Dict[str, Any] = field(default_factory=dict)
