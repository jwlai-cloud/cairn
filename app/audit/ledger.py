"""Append-only audit ledger.

Append-only to application users: entries are only ever added, never rewritten, so the
decision chain can be replayed from source event to outcome without the original
conversational state (docs/architecture/04-security-governance-and-safety.md 4.8).
"""

from __future__ import annotations

from typing import Any

from app.domain.models import AuditEntry, utcnow


class AuditLedger:
    def __init__(self, correlation_id: str) -> None:
        self.correlation_id = correlation_id
        self._entries: list[AuditEntry] = []

    def record(self, stage: str, actor: str, summary: str, **refs: Any) -> AuditEntry:
        entry = AuditEntry(
            seq=len(self._entries) + 1,
            at=utcnow(),
            stage=stage,
            actor=actor,
            summary=summary,
            refs={k: v for k, v in refs.items() if v is not None},
        )
        self._entries.append(entry)
        return entry

    @property
    def entries(self) -> list[AuditEntry]:
        return list(self._entries)
