"""Model selection must not depend on a hard-coded id that rots."""

import app.agents.bedrock_models as bm


def test_an_explicit_choice_always_wins(monkeypatch):
    monkeypatch.setattr(bm, "_candidates", lambda region: ["us.anthropic.claude-opus-5-v1:0"])
    assert bm.resolve_model_id("us-east-1", "us.amazon.nova-lite-v1:0") == "us.amazon.nova-lite-v1:0"


def test_the_newest_family_available_is_preferred(monkeypatch):
    monkeypatch.setattr(bm, "_candidates", lambda region: [
        "us.amazon.nova-lite-v1:0",
        "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        "us.anthropic.claude-sonnet-5-20260210-v1:0",
        "openai.gpt-oss-120b-1:0",
    ])
    assert bm.resolve_model_id("us-east-1") == "us.anthropic.claude-sonnet-5-20260210-v1:0"


def test_a_newer_dated_revision_is_picked_up_without_a_code_change(monkeypatch):
    monkeypatch.setattr(bm, "_candidates", lambda region: [
        "us.anthropic.claude-sonnet-5-20260210-v1:0",
        "us.anthropic.claude-sonnet-5-20261130-v1:0",
    ])
    assert bm.resolve_model_id("us-east-1").endswith("20261130-v1:0")


def test_cross_region_profiles_are_preferred_over_bare_model_ids(monkeypatch):
    monkeypatch.setattr(bm, "_candidates", lambda region: [
        "anthropic.claude-sonnet-4-5-20250929-v1:0",
        "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    ])
    assert bm.resolve_model_id("us-east-1").startswith("us.")


def test_a_locked_down_account_falls_back_rather_than_failing_here(monkeypatch):
    """Listing is denied on many accounts. Fail at invoke with a clear error, not here."""
    monkeypatch.setattr(bm, "_candidates", lambda region: [])
    assert bm.resolve_model_id("us-east-1") == bm.FALLBACK_MODEL_ID


def test_an_unranked_model_is_still_usable(monkeypatch):
    monkeypatch.setattr(bm, "_candidates", lambda region: ["some.future-model-v9:0"])
    assert bm.resolve_model_id("us-east-1") == "some.future-model-v9:0"


def test_region_is_not_forced_when_nothing_is_configured(monkeypatch):
    """Forcing us-east-1 would override AWS_DEFAULT_REGION, profiles and task roles."""
    for name in ("CAIRN_BEDROCK_REGION", "AWS_REGION", "AWS_DEFAULT_REGION"):
        monkeypatch.delenv(name, raising=False)
    import importlib

    from app.config import settings

    importlib.reload(settings)
    assert settings.BEDROCK_REGION is None


def test_the_standard_aws_region_variables_are_honoured(monkeypatch):
    import importlib

    from app.config import settings

    monkeypatch.delenv("CAIRN_BEDROCK_REGION", raising=False)
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-central-1")
    importlib.reload(settings)
    assert settings.BEDROCK_REGION == "eu-central-1"
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
    importlib.reload(settings)


def test_the_audit_names_the_model_that_actually_ran():
    from app.agents.graph import resolve_model_id_for
    from app.domain.models import MODEL_ID_FIXTURE

    assert resolve_model_id_for("fixture") == MODEL_ID_FIXTURE


def test_the_preference_list_matches_real_bedrock_id_conventions(monkeypatch):
    """Two conventions coexist: bare 5.x family ids and dated 4.x ids. Both must rank."""
    monkeypatch.setattr(bm, "_candidates", lambda region: [
        "us.anthropic.claude-haiku-4-5-20251001-v1:0",
        "us.amazon.nova-lite-v1:0",
        "us.openai.gpt-5.6-luna",
        "us.anthropic.claude-sonnet-5",
    ])
    assert bm.resolve_model_id("us-east-1") == "us.anthropic.claude-sonnet-5"


def test_a_newer_claude_4_x_outranks_an_older_one(monkeypatch):
    monkeypatch.setattr(bm, "_candidates", lambda region: [
        "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        "us.anthropic.claude-opus-4-8",
    ])
    assert bm.resolve_model_id("us-east-1") == "us.anthropic.claude-opus-4-8"


def test_the_three_models_adr_004_selects_are_all_ranked():
    """ADR-004 enables Sonnet 5, GPT-5.6 Luna and Nova Lite. All must be selectable."""
    for family in ("claude-sonnet-5", "gpt-5.6-luna", "nova-lite"):
        assert family in bm.PREFERENCE, f"{family} is not in the preference list"


def test_the_fallback_is_a_currently_valid_id():
    """The fallback fires when listing is denied; a stale id would fail confusingly."""
    assert bm.FALLBACK_MODEL_ID == "us.anthropic.claude-sonnet-5"


async def test_the_model_is_resolved_once_per_graph_not_once_per_node(monkeypatch):
    """Per-node resolution could give nodes different models and misreport the run."""
    import app.agents.graph as graph_module
    from app.agents.context import GraphContext
    from app.integrations.fixture_source import FixtureSource

    calls: list[str] = []
    original = graph_module.resolve_model_id_for

    def counted(mode: str) -> str:
        calls.append(mode)
        return original(mode)

    monkeypatch.setattr(graph_module, "resolve_model_id_for", counted)

    source = FixtureSource()
    ctx = GraphContext(
        tuple(source.events()), tuple(source.evidence()), source.site_model(), source.baseline_kpi()
    )
    result = await graph_module.run_graph("x", ctx)

    assert len(calls) == 1, f"resolved {len(calls)} times for a five-node graph"
    assert result.model_id == original("fixture")


async def test_an_explicit_model_id_is_used_without_resolving_at_all(monkeypatch):
    """The run service names the model in the audit first, then passes it down."""
    import app.agents.graph as graph_module
    from app.agents.context import GraphContext
    from app.integrations.fixture_source import FixtureSource

    def explode(_mode: str) -> str:
        raise AssertionError("must not resolve when the caller supplied a model id")

    monkeypatch.setattr(graph_module, "resolve_model_id_for", explode)
    source = FixtureSource()
    ctx = GraphContext(
        tuple(source.events()), tuple(source.evidence()), source.site_model(), source.baseline_kpi()
    )
    result = await graph_module.run_graph("x", ctx, model_id="pinned-for-this-run")
    assert result.model_id == "pinned-for-this-run"
