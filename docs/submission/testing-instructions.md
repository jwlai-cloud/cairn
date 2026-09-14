# Testing instructions (paste into the Devpost field)

**The full Strands agent graph runs in this demo.** Four specialist agents execute in
parallel, hooks cancel any tool call outside a node's allow-list, and every edge carries a
Pydantic contract enforced through Strands' forced tool call.

What the hosted link swaps is only the **model provider** behind that graph. Strands
exposes a `Model` interface; `BedrockModel` is one implementation and this project ships
another that returns deterministic output from fixtures. That is what lets you assess it
with no AWS account, no credentials and no API keys, and get the same result every time.

The same graph runs against a real model, and **the demo video is that run**: the header
reads `mode bedrock` naming `us.amazon.nova-lite-v1:0`, the decision loop fills over
nine, five and eight seconds of genuine inference rather than the ~40ms the deterministic
provider takes, and the incident narrative and scenario titles on screen are the model's
words, not fixtures. The hosted link is the deterministic one, so that you can assess it
with no credentials. The smoke test at the end of this page reproduces the Nova run.

## Hosted

<https://cairn-320877670799.us-central1.run.app>

First load takes a few seconds, since the service scales to zero when idle. Then, in
order:

1. **Inject all** — five signals from four source systems land on the timeline.
2. **Run analysis** — four specialist agents run in parallel in a bounded Strands graph.
   The decision loop on the left fills as each finishes, with measured milliseconds.
3. Click any of the three **recovery options**. They trade different things away.
4. **Attempt interlock override** — refused. Tier 4, rule id shown, and
   `decidedBy: deterministic policy service (no model call)`. This is the one to look at:
   no model is in that decision path.
5. **Request approval**, then **Approve as SHIFT_SUPERVISOR** — the token is scoped,
   bound to the plan version, expiring and single-use.
6. **Simulate dispatch timeout** — the outcome is held UNKNOWN. **Right-click Reconcile**
   to attempt a blind retry: refused with RECONCILIATION_REQUIRED. Then **Reconcile
   outcome** to close it properly.
7. **Audit trace** — the whole decision reconstructs: event, evidence, findings, policy,
   approval, action, outcome.

Every visitor gets their own run, so two people testing at once do not collide.

## From the repository

Requires Python 3.12 and uv. No Node, no build step, no AWS account.

    git clone https://github.com/jwlai-cloud/cairn.git && cd cairn
    uv venv && uv pip install -e ".[dev]"
    uv run python -m uvicorn app.api.main:app --port 8000
    # then open http://127.0.0.1:8000

Verification suites:

    uv run pytest -q                 # 126 tests
    uv run python -m app.evaluation   # 13 evaluation cases

## Optional: run it against a real model

Bedrock mode runs the same graph and the same governance against a real provider. It needs
credentials and is not required to assess the project.

    CAIRN_MODE=bedrock CAIRN_BEDROCK_MODEL_ID=us.amazon.nova-lite-v1:0 \
      uv run python -m app.agents.smoke

Verified against `us.amazon.nova-lite-v1:0`: the full graph completes in 13-17 seconds,
all five nodes satisfy their typed contracts, and every specialist calls tools before
answering.

## What is simulated

All data is synthetic. No mine system, PLC, SCADA, dispatch, ERP or CMMS is connected, and
there is no control path to operational technology. Every artefact the demo produces is
prefixed SIM.
