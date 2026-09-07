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
