"""AR-15: the decision chain must survive a process restart.

This was the one requirement in the TOGAF compliance assessment marked Deferred.
"""

import sqlite3

import pytest

from app.audit.ledger import AuditLedger
from app.audit.store import InMemoryAuditStore, SqliteAuditStore, build_store
from app.domain.run_service import CORRELATION_ID, Run, RunStore


async def _golden(run: Run) -> Run:
    run.inject_all_events()
    await run.analyse()
    run.request_approval("scn_recover_tonnes", actor_roles=["SHIFT_BOSS"])
    run.decide_approval(approve=True, approver_id="u", approver_role="SHIFT_BOSS")
    run.execute_approved_actions(actor_id="u", actor_roles=["SHIFT_BOSS"])
    run.verify_outcome()
    return run


def test_build_store_defaults_to_memory():
    assert isinstance(build_store(None), InMemoryAuditStore)
    assert isinstance(build_store(":memory:"), SqliteAuditStore)


async def test_the_audit_survives_a_restart(tmp_path):
    """Write with one store, then open a brand new one over the same file."""
    database = tmp_path / "audit.sqlite3"

    first = RunStore(audit_database=str(database))
    await _golden(first.run)
    written = [e.stage for e in first.run.view().audit]
    assert "OUTCOME_VERIFIED" in written
    first.audit_store.close()

    # A different process would do exactly this: open the file and read.
    reopened = SqliteAuditStore(database)
    recovered = reopened.entries_for_correlation(CORRELATION_ID)
    assert [e.stage for e in recovered] == written
    assert [e.seq for e in recovered] == list(range(1, len(written) + 1))
    for required in ("EVENT_INGESTED", "TOOL_CALL", "POLICY_DECISION",
                     "APPROVAL_GRANTED", "ACTION_EXECUTED", "OUTCOME_VERIFIED"):
        assert required in [e.stage for e in recovered]
    reopened.close()


async def test_a_reset_starts_a_new_run_without_erasing_the_old_one(tmp_path):
    store = RunStore(audit_database=str(tmp_path / "audit.sqlite3"))
    await _golden(store.run)
    first_count = len(store.run.view().audit)

    store.reset()
    assert store.run.view().audit == [], "a fresh run starts with a clean ledger view"
    await _golden(store.run)

    assert len(store.run.view().audit) == first_count, "the replay records the same chain"
    assert len(store.audit_history()) == first_count * 2, "and history keeps both runs"
    store.audit_store.close()


def test_the_database_refuses_updates_and_deletes(tmp_path):
    """Append-only is enforced where the data lives, not by convention in the code."""
    database = tmp_path / "audit.sqlite3"
    store = SqliteAuditStore(database)
    ledger = AuditLedger(CORRELATION_ID, store=store)
    ledger.record("EVENT_INGESTED", "test", "an entry that must not be rewritten")

    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        store._connection.execute("UPDATE audit_entries SET summary = 'tampered'")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        store._connection.execute("DELETE FROM audit_entries")

    assert store.entries_for_correlation(CORRELATION_ID)[0].summary.endswith("must not be rewritten")
    store.close()


async def test_durability_does_not_change_the_decision(tmp_path):
    """Swapping the store must not perturb the replay signature."""
    memory = Run()
    durable = Run(audit_store=SqliteAuditStore(tmp_path / "audit.sqlite3"))
    await _golden(memory)
    await _golden(durable)
    assert memory.replay_signature() == durable.replay_signature()


async def test_two_runs_sharing_a_store_keep_separate_ledgers(tmp_path):
    store = SqliteAuditStore(tmp_path / "audit.sqlite3")
    a = Run(audit_store=store)
    b = Run(audit_store=store)
    a.inject_all_events()
    b.inject_next_event()
    assert len(a.view().audit) == 5
    assert len(b.view().audit) == 1
    assert len(store.entries_for_correlation(CORRELATION_ID)) == 6
    store.close()


def test_refs_round_trip_with_the_same_shape_through_both_stores(tmp_path):
    """An entry read back from disk must look identical to the one held in memory."""
    from datetime import datetime, timezone

    from app.domain.models import Severity, ToolCallRecord

    refs = {
        "toolCall": ToolCallRecord(tool_name="get_evidence", status="success", duration_ms=3),
        "severity": Severity.HIGH,
        "at": datetime(2026, 9, 6, 14, 3, tzinfo=timezone.utc),
        "evidenceIds": ("evd_a", "evd_b"),
        "nested": {"count": 2, "flags": [True, False]},
        "dropped": None,
    }

    memory = AuditLedger(CORRELATION_ID, store=InMemoryAuditStore())
    durable = AuditLedger(CORRELATION_ID, store=SqliteAuditStore(tmp_path / "audit.sqlite3"))
    memory.record("TOOL_CALL", "risk", "read the evidence", **refs)
    durable.record("TOOL_CALL", "risk", "read the evidence", **refs)

    assert memory.entries[0].refs == durable.entries[0].refs
    assert "dropped" not in durable.entries[0].refs
    assert durable.entries[0].refs["severity"] == "HIGH"
    assert durable.entries[0].refs["evidenceIds"] == ["evd_a", "evd_b"]
    assert durable.entries[0].refs["toolCall"]["toolName"] == "get_evidence"
    durable.store.close()


def test_a_failed_append_does_not_consume_a_sequence_number():
    """A gap in the chain would be indistinguishable from a deleted entry."""

    class FlakyStore(InMemoryAuditStore):
        fail_next = False

        def append(self, correlation_id, run_key, entry):
            if self.fail_next:
                self.fail_next = False
                raise sqlite3.OperationalError("database is locked")
            super().append(correlation_id, run_key, entry)

    store = FlakyStore()
    ledger = AuditLedger(CORRELATION_ID, store=store)
    ledger.record("EVENT_INGESTED", "a", "first")

    store.fail_next = True
    with pytest.raises(sqlite3.OperationalError):
        ledger.record("EVENT_INGESTED", "b", "lost to a locked database")

    ledger.record("EVENT_INGESTED", "c", "next successful entry")
    seqs = [e.seq for e in ledger.entries]
    assert seqs == [1, 2], f"sequence must not skip a number, got {seqs}"
