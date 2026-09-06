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

    view = api_client.post("/v1/approvals/decision", json={"approve": True, "approverRole": "SHIFT_BOSS"}).json()
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
