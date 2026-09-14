import pytest

from app.domain.run_service import Run


@pytest.fixture
async def analysed_run() -> Run:
    """A run with every event injected and the bounded graph completed."""
    run = Run()
    run.inject_all_events()
    await run.analyse()
    return run


@pytest.fixture
def api_client():
    from fastapi.testclient import TestClient

    from app.api.main import app, store

    # Every visitor gets their own run, so tests start from an empty session table and
    # let the TestClient carry the session cookie between requests.
    store.clear()
    with TestClient(app) as client:
        yield client
