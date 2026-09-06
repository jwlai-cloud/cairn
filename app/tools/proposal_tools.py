"""Proposal tools.

Tier 2. These produce artefacts and estimates without changing any external system.
The arithmetic lives here rather than in a prompt so the numbers on a scenario card are
reproducible and testable.
"""

from __future__ import annotations

from app.domain.models import Kpi, ScenarioOption


def calculate_production_impact(baseline: Kpi, option: ScenarioOption) -> Kpi:
    """Project the shift KPI if this option is taken. Pure function of the fixture."""
    tonnes = baseline.tonnes_moved + option.impacts.estimated_tonnes_delta
    availability = round(
        baseline.crusher_availability_percent * (1.0 + option.impacts.estimated_throughput_delta), 1
    )
    return Kpi(
        tonnes_moved=tonnes,
        tonnes_target=baseline.tonnes_target,
        crusher_availability_percent=availability,
        active_trucks=baseline.active_trucks,
        weather_window_minutes=baseline.weather_window_minutes,
        unresolved_risks=baseline.unresolved_risks,
    )


def draft_work_order(option: ScenarioOption, asset_id: str) -> dict:
    return {
        "assetId": asset_id,
        "priority": "HIGH" if option.safety_risk_level.value in ("HIGH", "CRITICAL") else "MEDIUM",
        "description": f"{option.title}: {option.summary}",
        "scenarioId": option.scenario_id,
        "scenarioVersion": option.scenario_version,
    }


def draft_shift_instruction(option: ScenarioOption) -> dict:
    closed = ", ".join(option.closed_route_ids) or "none"
    return {
        "audience": "Shift A haul crews and dispatch",
        "instruction": (
            f"{option.title}. {option.summary} "
            f"Routes closed: {closed}. "
            f"Expected recovery {option.impacts.estimated_recovery_minutes} min."
        ),
        "scenarioId": option.scenario_id,
        "scenarioVersion": option.scenario_version,
    }


def check_spatial_temporal_conflicts(option: ScenarioOption, weather_window_minutes: int | None) -> list[str]:
    """Flag options whose recovery time runs past the weather window."""
    conflicts: list[str] = []
    if weather_window_minutes is None:
        return conflicts
    if option.impacts.estimated_recovery_minutes > weather_window_minutes and any(
        r not in option.closed_route_ids for r in option.route_overlay
    ):
        conflicts.append(
            f"Recovery of {option.impacts.estimated_recovery_minutes} min exceeds the "
            f"{weather_window_minutes} min weather window; part of the plan runs during rainfall."
        )
    return conflicts
