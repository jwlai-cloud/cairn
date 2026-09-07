"""Runtime configuration.

`fixture` is the default and the only mode that needs no credentials. `bedrock` is
opt-in via CAIRN_MODE and is not exercised by the test suite.
"""

from __future__ import annotations

import os

MODE = os.getenv("CAIRN_MODE", "fixture")

# A path makes the audit ledger durable across restarts (AR-15). Unset keeps the
# in-memory store, which is what the tests and the deterministic replay want.
AUDIT_DB = os.getenv("CAIRN_AUDIT_DB") or None
ACTOR_ID = os.getenv("CAIRN_ACTOR_ID", "user_shift_boss_01")
ACTOR_ROLES = tuple(os.getenv("CAIRN_ACTOR_ROLES", "SHIFT_BOSS,MAINTENANCE_PLANNER").split(","))

# Bedrock mode only. CAIRN needs a tool-capable model, not a specific vendor: the agent
# boundary is a Pydantic contract, so anything that can call a tool will do. Override to
# match whatever model access the account actually has.
BEDROCK_MODEL_ID = os.getenv("CAIRN_BEDROCK_MODEL_ID") or None
BEDROCK_REGION = (
    os.getenv("CAIRN_BEDROCK_REGION")
    or os.getenv("AWS_REGION")
    or os.getenv("AWS_DEFAULT_REGION")
    or None  # let the AWS SDK resolve it from the profile or task role
)
