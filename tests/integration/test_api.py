"""API-level demo path, including the error envelope."""


def test_health_needs_no_credentials(api_client):
    body = api_client.get("/healthz").json()
    assert body["status"] == "ok"
    assert body["mode"] == "fixture"
    assert body["credentialsRequired"] is False


def test_static_situation_room_is_served(api_client):
    assert api_client.get("/").status_code == 200
    for asset in ("/app.js", "/scene3d.js", "/scene2d.js", "/styles.css", "/vendor/three.module.js"):
        assert api_client.get(asset).status_code == 200, asset


def test_full_demo_path_over_http(api_client):
    assert api_client.post("/v1/events").json()["events"]
    view = api_client.post("/v1/runs/current/analyse").json()
    assert len(view["scenarios"]) == 3
    assert view["incident"]["weatherWindowMinutes"] == 42

    denied = api_client.post("/v1/actions/prohibited", json={"actionType": "OVERRIDE_SAFETY_INTERLOCK"})
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "POLICY_DENIED"
    assert denied.json()["error"]["correlationId"] == view["correlationId"]

    api_client.post("/v1/scenarios/scn_recover_tonnes/select")
    view = api_client.post("/v1/approvals", json={"scenarioId": "scn_recover_tonnes"}).json()
    assert view["approval"]["status"] == "PENDING"

    early = api_client.post("/v1/actions")
    assert early.status_code == 403, "an action before approval must be refused"

    view = api_client.post("/v1/approvals/decision", json={"approve": True, "approverRole": "SHIFT_SUPERVISOR"}).json()
    assert view["approval"]["status"] == "APPROVED"
    assert view["approval"]["approvalToken"]

    view = api_client.post("/v1/actions").json()
    assert all(a["simulated"] for a in view["actions"])
    view = api_client.post("/v1/outcome/verify").json()
    assert view["outcome"]["verified"] is True

    audit = api_client.get(f"/v1/audit/{view['correlationId']}").json()
    assert len(audit["entries"]) > 15


def test_reset_restores_a_clean_run(api_client):
    api_client.post("/v1/runs/current/analyse")
    before = api_client.get("/v1/runs/current/signature").json()["replaySignature"]
    view = api_client.post("/v1/runs/current/reset").json()
    assert view["events"] == [] and view["scenarios"] == []
    api_client.post("/v1/runs/current/analyse")
    after = api_client.get("/v1/runs/current/signature").json()["replaySignature"]
    assert before == after


def test_unknown_scenario_is_a_404(api_client):
    api_client.post("/v1/runs/current/analyse")
    assert api_client.get("/v1/scenarios/scn_nope").status_code == 404


def test_two_visitors_get_independent_runs():
    """A shared demo link must not let one visitor's Reset wipe another's demo."""
    from fastapi.testclient import TestClient

    from app.api.main import app, store

    store.clear()
    with TestClient(app) as alice, TestClient(app) as bob:
        alice.post("/v1/events")
        assert len(alice.get("/v1/runs/current").json()["events"]) == 5
        assert bob.get("/v1/runs/current").json()["events"] == [], "bob sees alice's events"

        bob.post("/v1/events")
        alice.post("/v1/runs/current/reset")
        assert alice.get("/v1/runs/current").json()["events"] == []
        assert len(bob.get("/v1/runs/current").json()["events"]) == 5, "alice's reset wiped bob"
        assert store.session_count == 2


def test_a_session_cookie_is_issued_and_reused():
    from fastapi.testclient import TestClient

    from app.api.main import SESSION_COOKIE, app, store

    store.clear()
    with TestClient(app) as client:
        first = client.get("/v1/runs/current")
        assert SESSION_COOKIE in first.cookies or SESSION_COOKIE in client.cookies
        sid = client.cookies.get(SESSION_COOKIE)
        assert sid and len(sid) >= 16
        client.get("/v1/runs/current")
        assert client.cookies.get(SESSION_COOKIE) == sid, "session must be stable across calls"
        assert store.session_count == 1


def test_sessions_are_capped_and_evicted():
    """A public link is an unbounded number of visitors; this store lives in memory."""
    from app.domain.run_service import SessionRunStore

    small = SessionRunStore(max_sessions=3)
    for i in range(6):
        small.run_for(f"visitor-{i}")
    assert small.session_count == 3


def test_audit_history_is_scoped_to_the_session():
    from fastapi.testclient import TestClient

    from app.api.main import app, store

    store.clear()
    with TestClient(app) as alice, TestClient(app) as bob:
        alice.post("/v1/events")
        a = alice.get("/v1/audit/corr_compound_disruption_v1/history").json()
        b = bob.get("/v1/audit/corr_compound_disruption_v1/history").json()
        assert a["entryCount"] == 5
        assert b["entryCount"] == 0, "bob must not see alice's audit entries"
