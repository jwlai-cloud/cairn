"""Append-only audit ledger.

Append-only to application users: entries are only ever added, never rewritten, so the
decision chain can be replayed from source event to outcome without the original
conversational state (docs/architecture/04 4.8).

The ledger owns sequencing and delegates persistence to an AuditStore, so the same
code path serves the hermetic in-memory default and the durable SQLite store.
"""

from __future__ import annotations

import time
from typing import Any

from app.audit.store import AuditStore, InMemoryAuditStore
from app.domain.models import AuditEntry, utcnow


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
        self._count += 1
        entry = AuditEntry(
            seq=self._count,
            at=utcnow(),
            stage=stage,
            actor=actor,
            summary=summary,
            refs={k: v for k, v in refs.items() if v is not None},
        )
        self.store.append(self.correlation_id, self.run_key, entry)
        return entry

    @property
    def entries(self) -> list[AuditEntry]:
        return self.store.entries_for_run(self.run_key)
