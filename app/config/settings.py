"""Runtime configuration.

`fixture` is the default and the only mode that needs no credentials. `bedrock` is
opt-in via CAIRN_MODE and is not exercised by the test suite.
"""

from __future__ import annotations

import os

MODE = os.getenv("CAIRN_MODE", "fixture")
ACTOR_ID = os.getenv("CAIRN_ACTOR_ID", "user_shift_boss_01")
ACTOR_ROLES = tuple(os.getenv("CAIRN_ACTOR_ROLES", "SHIFT_BOSS,MAINTENANCE_PLANNER").split(","))
