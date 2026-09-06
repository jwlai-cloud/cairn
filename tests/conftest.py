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

    store.reset()
    with TestClient(app) as client:
        yield client
