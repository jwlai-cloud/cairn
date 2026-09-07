"""Append-only audit ledger.

Append-only to application users: entries are only ever added, never rewritten, so the
decision chain can be replayed from source event to outcome without the original
conversational state (docs/architecture/04-security-governance-and-safety.md 4.8).

The ledger owns sequencing and delegates persistence to an AuditStore, so the same
code path serves the hermetic in-memory default and the durable SQLite store.
"""

from __future__ import annotations

import time
from typing import Any

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel

from app.audit.store import AuditStore, InMemoryAuditStore
from app.domain.models import AuditEntry, utcnow


def jsonable(value: Any) -> Any:
    """Reduce a reference value to something JSON round-trips unchanged.

    Normalising here rather than in the SQLite encoder keeps the two stores honest:
    an entry read back from disk has the same shape as the one held in memory, so a
    test cannot pass against one store and fail against the other.
    """
    if isinstance(value, BaseModel):
        return value.model_dump(by_alias=True, mode="json")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [jsonable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


class AuditLedger:
    def __init__(
        self,
        correlation_id: str,
        store: AuditStore | None = None,
        run_key: str | None = None,
    ) -> None:
        self.correlation_id = correlation_id
        self.store: AuditStore = store or InMemoryAuditStore()
        # Distinguishes one run from a replay of the same scenario. Excluded from the
        # replay signature, so it cannot make two identical runs look different.
        self.run_key = run_key or f"{correlation_id}:{time.time_ns()}"
        self._count = 0

    def record(self, stage: str, actor: str, summary: str, **refs: Any) -> AuditEntry:
        # Take the next sequence number without consuming it. A durable append can fail
        # on a lock or a full disk; consuming the number first would leave a permanent
        # gap in the chain and silently drop the entry that owned it.
        entry = AuditEntry(
            seq=self._count + 1,
            at=utcnow(),
            stage=stage,
            actor=actor,
            summary=summary,
            refs={k: jsonable(v) for k, v in refs.items() if v is not None},
        )
        self.store.append(self.correlation_id, self.run_key, entry)
        self._count = entry.seq
        return entry

    @property
    def entries(self) -> list[AuditEntry]:
        return self.store.entries_for_run(self.run_key)
