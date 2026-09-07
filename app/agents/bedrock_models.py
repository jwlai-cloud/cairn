"""Pick a Bedrock model instead of hard-coding one.

A pinned model id rots: it is wrong the moment the provider ships a newer model, and
wrong again on an account that never enabled that one. CAIRN only needs a tool-capable
model - the agent boundary is a Pydantic contract - so the right behaviour is to ask the
account what it has and take the best of it.

Order of precedence:
1. CAIRN_BEDROCK_MODEL_ID, if set. An explicit choice always wins.
2. Discovery: list what the account can actually reach and rank it.
3. A conservative fallback, so a locked-down IAM policy degrades to a clear
   AccessDenied at invoke time rather than a confusing empty result here.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Newest and most capable first. Substring match against the model or profile id, so a
# new dated revision of the same family is picked up without a code change.
#
# Two id conventions coexist on Bedrock. The 5.x Anthropic and OpenAI models use a bare
# family id ("anthropic.claude-sonnet-5"); older ones carry a date and version suffix
# ("anthropic.claude-haiku-4-5-20251001-v1:0"). Substring matching handles both.
PREFERENCE: tuple[str, ...] = (
    "claude-opus-5",
    "claude-sonnet-5",
    "claude-haiku-5",
    "claude-opus-4-8",
    "claude-opus-4-7",
    "claude-opus-4-6",
    "claude-sonnet-4-6",
    "claude-opus-4-5",
    "claude-sonnet-4-5",
    "claude-haiku-4-5",
    "gpt-5.6-sol",
    "gpt-5.6-luna",
    "nova-2-pro",
    "nova-2-lite",
    "nova-premier",
    "nova-pro",
    "nova-lite",
    "gpt-oss",
    "llama4",
    "llama3-3",
)

FALLBACK_MODEL_ID = "us.anthropic.claude-sonnet-5"


def _candidates(region: str | None) -> list[str]:
    """Every model id this account can name, cross-region profiles preferred."""
    try:
        import boto3
    except ImportError:  # pragma: no cover - boto3 ships with strands
        return []

    client = boto3.client("bedrock", region_name=region)  # region=None -> SDK default
    ids: list[str] = []

    try:
        paginator = client.get_paginator("list_inference_profiles")
        for page in paginator.paginate():
            ids += [p["inferenceProfileId"] for p in page.get("inferenceProfileSummaries", [])]
    except Exception as exc:
        logger.debug("bedrock inference profiles unavailable: %s", exc)

    try:
        response = client.list_foundation_models()
        ids += [
            m["modelId"]
            for m in response.get("modelSummaries", [])
            if "ON_DEMAND" in (m.get("inferenceTypesSupported") or [])
        ]
    except Exception as exc:
        logger.debug("bedrock foundation models unavailable: %s", exc)

    return ids


def discover_model_id(region: str | None) -> str | None:
    """Best available model id, or None when the account will not say."""
    ids = _candidates(region)
    if not ids:
        return None
    for family in PREFERENCE:
        matches = sorted((i for i in ids if family in i), reverse=True)
        if matches:
            # Cross-region inference profiles ("us.", "eu.") have better availability.
            profiles = [i for i in matches if i.split(".")[0] in ("us", "eu", "apac")]
            return (profiles or matches)[0]
    return sorted(ids)[0]


def resolve_model_id(region: str | None = None, configured: str | None = None) -> str:
    if configured:
        return configured
    discovered = discover_model_id(region)
    if discovered:
        logger.info("bedrock: selected %s by discovery", discovered)
        return discovered
    logger.warning(
        "bedrock: could not list models in %s (missing bedrock:ListFoundationModels?); "
        "falling back to %s. Set CAIRN_BEDROCK_MODEL_ID to choose explicitly.",
        region or "the SDK default region", FALLBACK_MODEL_ID,
    )
    return FALLBACK_MODEL_ID
