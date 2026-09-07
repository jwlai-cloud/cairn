# ADR-004: Bedrock model selection

**Status:** Accepted · **Date:** 2026-09-07 · **Supersedes:** nothing · **Amends:** ADR-001

## Context

ADR-001 chose Python, Strands and Amazon Bedrock, but named no model. The code then pinned
`us.anthropic.claude-sonnet-4-5-20250929-v1:0` by default, which was wrong twice over: newer
generations had shipped, and the account had access to none of them.

A pinned id is a design smell rather than a stale constant. CAIRN needs a **tool-capable**
model and nothing more — the agent boundary is a Pydantic contract enforced through Strands'
client-side tool calling, so vendor identity is a cost and availability question, not a
capability one.

Two Bedrock id conventions now coexist, which is why the first round of probing failed:

| Generation | Convention | Example |
|---|---|---|
| 5.x Anthropic, OpenAI | bare family id | `us.anthropic.claude-sonnet-5` |
| 4.x and earlier, Nova | dated, versioned | `us.anthropic.claude-haiku-4-5-20251001-v1:0` |

## What the account can actually reach

Enumerated by invoking each candidate and reading the error: `AccessDeniedException` means the
model exists and is not enabled, `ValidationException` means the id is wrong. `ListFoundationModels`
is denied on this account, so this was the only available method.

Present but not enabled: Claude Opus 5, Sonnet 5, Opus 4.8, Sonnet 4.6, Opus 4.5, Opus 4.1,
Haiku 4.5; GPT-5.6 Sol, GPT-5.6 Luna, gpt-oss 120b/20b; Nova 2 Lite, Nova Premier/Pro/Lite/Micro;
Llama 4 Maverick, Llama 3.3 70B; DeepSeek-R1; Pixtral Large; Jamba 1.5 Large; Palmyra X5.

## Decision

Enable three models, each for a stated reason.

| Role | Model | Id | Why this one |
|---|---|---|---|
| Primary | Claude Sonnet 5 | `us.anthropic.claude-sonnet-5` | Aligned with ADR-001. Tool use certain, 1M context, strongest of the affordable tier. |
| Portability proof | GPT-5.6 Luna | `us.openai.gpt-5.6-luna` | A different vendor running the identical typed contracts is what makes the provider-neutrality claim observable rather than asserted. |
| Smoke test | Nova Lite | `us.amazon.nova-lite-v1:0` | Cheapest path to "does a real model satisfy the contract at all", and first-party so access is usually immediate. |

Cost against CAIRN's workload. The figures below are **corrected against a real run**:
two Bedrock runs on 2026-09-07 measured 30,253 and 31,818 input tokens, and 2,504 and
4,006 output. The original estimate of 15,357 input was roughly half the truth, so every
number in this table moved. Input is stable within five per cent, because it is the
fixture plus the prompts; output varies by about sixty per cent, because it is the
model's verbosity. Input therefore dominates at roughly twelve to one, and the input
rate is what sets the cost.

Basis: 31,000 input and 3,250 output tokens per graph run.
Raw measurement in `docs/architecture/measurements/nova-lite-run-2026-09-07.json`.

| Model | Per run | Evaluation suite (~16 runs) | $50 of credits |
|---|---|---|---|
| Claude Opus 5 | $0.2363 | $3.78 | ~212 runs |
| **Claude Sonnet 5** | **$0.0945** | $1.51 | ~529 runs |
| **GPT-5.6 Luna** (geo) | $0.0111 | $0.18 | ~4,500 runs |
| **Nova Lite** | rate not published on the model card | — | — |

Opus 5 is not enabled. At 2.5x Sonnet 5 for one demo it does not earn its place; if a showcase
run is wanted for the video it is a single ~$0.17 invocation.

## Consequences

**Selection is by discovery, not by constant.** `app/agents/bedrock_models.py` ranks whatever the
account can list, newest family first, and only falls back to a constant when listing is denied.
Enabling Sonnet 5 is therefore sufficient; no code change follows.

**Two capability traps are now documented rather than discovered later.**

- Every Claude and Nova card lists Bedrock's *Structured outputs* feature as **not supported**.
  This is harmless: Strands enforces typed output through **client-side tool calling**, which the
  Nova Lite and Haiku 4.5 cards list explicitly as supported. Reading only the first line would
  have caused a needless model change.
- GPT-5.6 Luna is the inverse — structured outputs supported, server-side tool use not supported,
  and client-side tool calling not listed either way. Luna is therefore an **experiment**, not a
  dependency. If it cannot satisfy the contract, that is a finding worth reporting, not a defect.
- Nova Lite caps output at 5K tokens. The scenario planner emits the largest single payload in the
  graph, so Nova Lite is a smoke test rather than a demo model. Nova 2 Lite is also available.

**IAM.** Strands calls `ConverseStream`, so `bedrock:InvokeModelWithResponseStream` is required and
is the action the smoke test reports as missing. Luna additionally needs `bedrock:InvokeModel` on
`arn:aws:bedrock:{region}:{account}:project/default`.

**Nothing about the default demo changes.** Fixture mode remains the default, needs no credentials,
and stays byte-identical on replay. Bedrock mode exists to show the same contracts hold against a
real model; it is not on the path a judge has to walk.

## Alternatives considered

**Pin Claude Opus 5 as primary.** Rejected: 2.5x the cost for a demo whose bottleneck is not model
capability. The reasoning work is deterministic policy, not generation.

**Leave the model pinned and simply update the constant.** Rejected: it would be wrong again at the
next release, and it was already wrong twice.

**Move off Bedrock to a direct provider.** Not considered here. That would contradict ADR-001 and
requires its own Phase A re-entry under `09 §9.11`, not a configuration change.
