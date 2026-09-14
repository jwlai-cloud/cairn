---
title: "Agents for Humans: the fixture that hid four bugs from me"
published: false
description: A deterministic model provider made my agent demo reproducible. It also kept four contract bugs green for weeks.
tags: aws, ai, python, architecture
# Set this to the builder.aws URL once that version is published, so the original
# is canonical and the cross-post is not indexed as a competing duplicate.
canonical_url:
---

I built an enterprise agent for mine operations and gave it a deterministic model provider so the demo would replay identically. That decision was right, and it hid four bugs from me for the entire project.

This is about what happened the day I first pointed it at a real model.

## The setup

CAIRN correlates fragmented signals from a mine shift into one incident, has four specialist agents analyse it in parallel through a bounded [Strands Agents](https://strandsagents.com) graph, and produces three recovery options. Then it refuses to act until a person signs.

To make it reproducible I wrote a Strands `Model` provider returning deterministic output from fixtures. No credentials, no network, byte-identical replay. CI ran against it. A thirteen-case evaluation suite ran against it. Everything was green.

## Then Nova Lite ran the same graph

The graph passed. All five nodes satisfied their typed contracts. Every specialist called tools before answering. Thirteen seconds, 30,253 input tokens.

And the output was unusable.

```text
key                    option_1             (the UI selects on recover_tonnes)
recommendedScenarioId  scenario_id_1        (matches none of its own options)
requiredApprovals      operations_manager   (not a role the policy table knows)
estimatedTonnesDelta   -1200, -1500, -1000  (every option a loss)
```

Pydantic validated all of it. Every field was present and correctly typed.

## Why the fixture hid it

Look at what the contract actually said:

```python
key: str  # protect_safety | recover_tonnes | preserve_equipment
```

The legal values were in a **comment**. The model never sees comments. It sees the JSON schema Strands generates for its forced tool call, and that schema said `string`.

`requiredApprovals` was `list[str]`, so any plausible role name validated. `recommendedScenarioId` was `str`, so it could point at nothing — and did. The tonnes sign convention was written down nowhere at all, so the model read the delta as a loss against an undisrupted plan while the fixture meant recovery against doing nothing. Both readings are defensible. That is the problem.

Each of those was latent and green for weeks, because the fixture always wrote the right value. My tests asserted against a provider that happened to behave.

## The fix, and the thing worth generalising

Four constraints moved out of comments and into the schema: two enums, a model validator for referential integrity, and a field description stating the sign convention. Then five tests that assert the **schema** rather than a provider, so they need no credentials and hold for any model. All five fail against the old contract.

> Anything whose correctness depends on a provider must be asserted against the schema, not against the provider.

A comment is not a constraint. It documents intent to humans and enforces nothing on the machine that actually consumes your contract.

## A second thing the fixture hid

While I was in there, I asked why the risk agent made two tool calls when the others made three. The answer was boring — its plan is two. But checking turned up something else: three of my prompts advertised tools that do not exist.

```markdown
## Allowed tools
`get_weather_window`, `get_active_permits`, `get_evidence`, `get_site_context`
```

`get_active_permits` exists nowhere in the codebase. The scenario planner's prompt offered three tools while its allow-list is empty by design, and one of those three was fictional too.

The fixture provider follows a tool plan and never reads the prompt. Only a real model reads the prompt, tries to call a tool that is not there, and gets cancelled by the hook. The guard held — but the attempt is wasted and the trajectory polluted.

Two tests now assert that a prompt's advertised tools equal its node's allow-list, and that every advertised tool is registered.

## What I would do differently

Keep the deterministic provider. It is the right call: anyone can clone the repository and get the same result with no account, and CI has a hermetic gate. I would not give that up.

But run a real provider **early**, and treat the first run as a contract review rather than a smoke test. Every defect it found was a place where I had written the rule down somewhere the machine could not read it.

Both modes now run the same graph and the same governance. Swap the brain; the safety envelope does not move. That is a stronger claim than either mode alone, and I only earned it by running both.

---

*CAIRN is built with Python, the AWS Strands Agents SDK, and Amazon Bedrock. Everything in it is synthetic and simulation-only: no mine system, PLC, SCADA, dispatch, ERP or CMMS is connected, and there is no control path to operational technology by design.*

*Code: [github.com/jwlai-cloud/cairn](https://github.com/jwlai-cloud/cairn)*
