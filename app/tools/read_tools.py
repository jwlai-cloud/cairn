"""Read-only tools.

Tier 0. Safe by default but still scoped: every result carries provenance so a caller
can tell fresh fact from stale guess. Returns typed results, never raw source payloads.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.models import Asset, Evidence, Kpi, OperationalEvent, Route, SiteModel
from app.integrations.fixture_source import FixtureSource


@dataclass
class ReadTools:
    source: FixtureSource
    read_only: bool = True

    def get_site_context(self) -> SiteModel:
        return self.source.site_model()

    def get_asset_status(self, asset_id: str) -> Asset | None:
        return next((a for a in self.source.site_model().assets if a.asset_id == asset_id), None)

    def get_routes(self) -> list[Route]:
        return self.source.site_model().routes

    def get_recent_events(self, up_to_offset_seconds: int | None = None) -> list[OperationalEvent]:
        events = self.source.events()
        if up_to_offset_seconds is None:
            return events
        return [e for e in events if e.offset_seconds <= up_to_offset_seconds]

    def get_evidence(self, evidence_ids: list[str] | None = None) -> list[Evidence]:
        evidence = self.source.evidence()
        if evidence_ids is None:
            return evidence
        wanted = set(evidence_ids)
        return [e for e in evidence if e.evidence_id in wanted]

    def get_maintenance_constraints(self) -> list[OperationalEvent]:
        return [e for e in self.source.events() if e.event_type.value == "MAINTENANCE_CONSTRAINT"]

    def get_weather_window(self) -> OperationalEvent | None:
        return next((e for e in self.source.events() if e.event_type.value == "WEATHER_ALERT"), None)

    def get_production_constraints(self) -> list[OperationalEvent]:
        return [e for e in self.source.events() if e.event_type.value == "PRODUCTION_CONSTRAINT"]

    def get_baseline_kpi(self) -> Kpi:
        return self.source.baseline_kpi()
