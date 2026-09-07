"""Runtime configuration.

`fixture` is the default and the only mode that needs no credentials. `bedrock` is
opt-in via CAIRN_MODE and is not exercised by the test suite.
"""

from __future__ import annotations

import os

MODE = os.getenv("CAIRN_MODE", "fixture")
ACTOR_ID = os.getenv("CAIRN_ACTOR_ID", "user_shift_boss_01")
ACTOR_ROLES = tuple(os.getenv("CAIRN_ACTOR_ROLES", "SHIFT_BOSS,MAINTENANCE_PLANNER").split(","))

# Bedrock mode only. CAIRN needs a tool-capable model, not a specific vendor: the agent
# boundary is a Pydantic contract, so anything that can call a tool will do. Override to
# match whatever model access the account actually has.
BEDROCK_MODEL_ID = os.getenv("CAIRN_BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0")
BEDROCK_REGION = os.getenv("CAIRN_BEDROCK_REGION", os.getenv("AWS_REGION", "us-east-1"))
