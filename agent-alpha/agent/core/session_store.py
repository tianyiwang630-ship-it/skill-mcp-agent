"""
Persistent session snapshots for CLI recovery.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class SessionKind(StrEnum):
    INTERACTIVE = "interactive"
    CRON = "cron"
    SUBAGENT = "subagent"
    SYSTEM = "system"


@dataclass(slots=True)
class SessionRecord:
    session_id: str
    kind: SessionKind = SessionKind.INTERACTIVE
    workspace: str = ""
    history: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)

    @property
    def title(self) -> str:
        for message in self.history:
            if message.get("role") == "user":
                return str(message.get("content", "")).strip().replace("\n", " ")[:100]
        return ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["kind"] = self.kind.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionRecord":
        kind = data.get("kind", SessionKind.INTERACTIVE)
        return cls(
            session_id=data["session_id"],
            kind=kind if isinstance(kind, SessionKind) else SessionKind(str(kind)),
            workspace=str(data.get("workspace") or ""),
            history=list(data.get("history", [])),
            metadata=dict(data.get("metadata", {})),
            events=list(data.get("events", [])),
            created_at=data.get("created_at") or _now_iso(),
            updated_at=data.get("updated_at") or _now_iso(),
        )


class SessionStore:
    """Store and restore CLI session snapshots."""

    def __init__(self, sessions_dir: Path):
        self.sessions_dir = Path(sessions_dir).resolve()
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def _session_path(self, session_id: str) -> Path:
        return self.sessions_dir / f"{session_id}.json"

    def save(self, record: SessionRecord) -> SessionRecord:
        path = self._session_path(record.session_id)
        path.write_text(json.dumps(record.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return record

    def load(self, session_id: str) -> SessionRecord | None:
        path = self._session_path(session_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return SessionRecord.from_dict(data)

    def list_recent(
        self,
        *,
        kind: SessionKind | None = None,
        limit: int | None = 20,
    ) -> list[SessionRecord]:
        records: list[SessionRecord] = []
        for path in self.sessions_dir.glob("*.json"):
            try:
                record = SessionRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                continue
            if kind is not None and record.kind != kind:
                continue
            records.append(record)

        records.sort(key=lambda item: item.updated_at, reverse=True)
        return records[:limit] if limit is not None else records

    def update_workspace(
        self,
        session_id: str,
        workspace: str,
        *,
        changed_at: str | None = None,
    ) -> SessionRecord:
        record = self.load(session_id)
        if record is None:
            raise ValueError(f"Session not found: {session_id}")

        timestamp = changed_at or _now_iso()
        record.workspace = str(workspace)
        record.updated_at = timestamp
        record.events.append(
            {
                "type": "workspace_changed",
                "timestamp": timestamp,
                "workspace": str(workspace),
            }
        )
        self.save(record)
        return record
