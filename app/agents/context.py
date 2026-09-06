"""Typed input to the agent graph.

The graph is a function of this context. Entry-node reducers read it directly; the
scenario planner reads what the specialists made of it. Nothing in the agent layer
reaches back into the run service or the fixture files.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.models import Evidence, Kpi, OperationalEvent, SiteModel


@dataclass(frozen=True)
class GraphContext:
    events: tuple[OperationalEvent, ...]
    evidence: tuple[Evidence, ...]
    site: SiteModel
    baseline_kpi: Kpi

    # ------------------------------------------------------------- derived facts

    def of_type(self, event_type: str) -> tuple[OperationalEvent, ...]:
        return tuple(e for e in self.events if e.event_type.value == event_type)

    @property
    def crusher_capacity_percent(self) -> float:
        degraded = self.of_type("ASSET_DEGRADED")
        if not degraded:
            return 100.0
        return min(e.measurements.get("capacityPercent", 100.0) for e in degraded)

    @property
    def trucks_lost(self) -> int:
        return len({e.asset_id for e in self.of_type("ASSET_UNAVAILABLE") if e.asset_id})

    @property
    def available_trucks(self) -> int:
        return max(self.baseline_kpi.active_trucks - self.trucks_lost, 0)

    @property
    def weather_window_minutes(self) -> int | None:
        alerts = self.of_type("WEATHER_ALERT")
        if not alerts:
            return None
        return int(min(e.measurements.get("minutesToClosure", 0) for e in alerts))

    @property
    def exposed_route_ids(self) -> tuple[str, ...]:
        return tuple(e.route_id for e in self.of_type("WEATHER_ALERT") if e.route_id)

    @property
    def crew_free_in_minutes(self) -> int:
        constraints = self.of_type("MAINTENANCE_CONSTRAINT")
        if not constraints:
            return 0
        return int(max(e.measurements.get("crewFreeInMinutes", 0) for e in constraints))

    @property
    def stockpile_live_tonnes(self) -> int:
        constraints = self.of_type("PRODUCTION_CONSTRAINT")
        if not constraints:
            return 0
        return int(max(e.measurements.get("stockpileLiveTonnes", 0) for e in constraints))

    @property
    def disruption_index(self) -> float:
        """Combined severity of the crusher derate and the lost fleet capacity.

        Used to scale recovery cost. 0.375 is the value of the full five-event fixture,
        so the golden path reproduces its documented figures exactly.
        """
        capacity_loss = (100.0 - self.crusher_capacity_percent) / 100.0
        fleet_loss = self.trucks_lost / max(self.baseline_kpi.active_trucks, 1)
        return round(capacity_loss + fleet_loss, 6)

    def evidence_ids_for(self, *event_types: str) -> list[str]:
        ids: list[str] = []
        for event_type in event_types:
            for event in self.of_type(event_type):
                ids.extend(event.evidence_ids)
        return sorted(dict.fromkeys(ids))

    @property
    def stale_evidence_ids(self) -> tuple[str, ...]:
        return tuple(e.evidence_id for e in self.evidence if e.stale)

    @property
    def conflicting_pairs(self) -> tuple[tuple[str, str], ...]:
        seen: set[frozenset[str]] = set()
        pairs: list[tuple[str, str]] = []
        for e in self.evidence:
            for other in e.conflicts_with:
                key = frozenset({e.evidence_id, other})
                if key not in seen:
                    seen.add(key)
                    pairs.append(tuple(sorted(key)))  # type: ignore[arg-type]
        return tuple(pairs)


FULL_FIXTURE_DISRUPTION_INDEX = 0.375
"""Disruption index of the complete five-event scenario, used to normalise cost scaling."""
