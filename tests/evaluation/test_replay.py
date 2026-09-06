"""Reset and replay produce the same decision, options and audit chain."""

from app.domain.run_service import Run, RunStore


async def _golden(run: Run) -> Run:
    run.inject_all_events()
    await run.analyse()
    run.request_approval("scn_recover_tonnes", actor_roles=["SHIFT_BOSS"])
    run.decide_approval(approve=True, approver_id="user_shift_boss_01", approver_role="SHIFT_BOSS")
    run.execute_approved_actions(actor_id="user_shift_boss_01", actor_roles=["SHIFT_BOSS"])
    run.verify_outcome()
    return run


async def test_two_runs_produce_an_identical_replay_signature():
    first = await _golden(Run())
    second = await _golden(Run())
    assert first.replay_signature() == second.replay_signature()


async def test_reset_clears_all_run_state():
    store = RunStore()
    await _golden(store.run)
    assert store.run.gateway.records and store.run.outcome

    fresh = store.reset()
    assert fresh.events == []
    assert fresh.scenarios == []
    assert fresh.approval is None
    assert fresh.outcome is None
    assert fresh.gateway.records == []
    assert fresh.ledger.entries == []
    assert fresh.view().status.value == "IDLE"


async def test_replay_after_reset_matches_the_first_run():
    store = RunStore()
    first = (await _golden(store.run)).replay_signature()
    store.reset()
    second = (await _golden(store.run)).replay_signature()
    assert first == second


async def test_stepwise_injection_reaches_the_same_state_as_bulk():
    stepwise = Run()
    while stepwise.inject_next_event() is not None:
        pass
    await stepwise.analyse()

    bulk = Run()
    bulk.inject_all_events()
    await bulk.analyse()

    assert [e.event_id for e in stepwise.events] == [e.event_id for e in bulk.events]
    assert stepwise.replay_signature() == bulk.replay_signature()
