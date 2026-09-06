"""Deterministic synthetic mine fixtures.

Everything here is invented. No live mine system, PLC, SCADA, dispatch, ERP or CMMS
is contacted. The adapter interface below is what a real read-only site adapter would
implement, so the fixture can be swapped for a governed integration later.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from app.domain.models import (
    Asset,
    AssetState,
    DataClassification,
    Evidence,
    EventSource,
    EventType,
    Kpi,
    OperationalEvent,
    Point,
    Route,
    Severity,
    SiteModel,
)

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures"
SCENARIO_FILE = FIXTURE_DIR / "scenarios" / "compound-disruption.json"

# Fixed shift start makes every replay byte-identical.
SHIFT_START = datetime(2026, 9, 6, 14, 0, 0, tzinfo=timezone.utc)


class SiteReadModelSource(Protocol):
    """Read-only site adapter. A real adapter would sit behind the Zone 1 boundary."""

    def site_model(self) -> SiteModel: ...
    def baseline_kpi(self) -> Kpi: ...
    def events(self) -> list[OperationalEvent]: ...
    def evidence(self) -> list[Evidence]: ...


@lru_cache(maxsize=1)
def _raw() -> dict:
    return json.loads(SCENARIO_FILE.read_text())


def _dt(offset_seconds: int) -> datetime:
    return SHIFT_START + timedelta(seconds=offset_seconds)


class FixtureSource:
    """Deterministic in-repo implementation of SiteReadModelSource."""

    source_name = "fixture"

    def site_model(self) -> SiteModel:
        raw = _raw()["site"]
        return SiteModel(
            site_id=raw["siteId"],
            name=raw["name"],
            shift_label=raw["shiftLabel"],
            assets=[
                Asset(
                    asset_id=a["assetId"],
                    name=a["name"],
                    kind=a["kind"],
                    position=Point(**a["position"]),
                    state=AssetState(a.get("state", "NORMAL")),
                    capacity_percent=a.get("capacityPercent", 100.0),
                    detail=a.get("detail", ""),
                    home_route_id=a.get("homeRouteId"),
                )
                for a in raw["assets"]
            ],
            routes=[
                Route(
                    route_id=r["routeId"],
                    name=r["name"],
                    path=[Point(**p) for p in r["path"]],
                    open=r.get("open", True),
                    exposed_to_weather=r.get("exposedToWeather", False),
                    detail=r.get("detail", ""),
                )
                for r in raw["routes"]
            ],
        )

    def baseline_kpi(self) -> Kpi:
        return Kpi(**_raw()["baselineKpi"])

    def events(self) -> list[OperationalEvent]:
        out: list[OperationalEvent] = []
        for e in _raw()["events"]:
            offset = e["offsetSeconds"]
            out.append(
                OperationalEvent(
                    event_id=e["eventId"],
                    event_type=EventType(e["eventType"]),
                    source=EventSource(
                        system=e["source"]["system"],
                        source_record_id=e["source"]["sourceRecordId"],
                        observed_at=_dt(offset - e["source"].get("observationLagSeconds", 0)),
                        received_at=_dt(offset),
                    ),
                    site_id=e["siteId"],
                    asset_id=e.get("assetId"),
                    route_id=e.get("routeId"),
                    location_id=e.get("locationId"),
                    severity=Severity(e["severity"]),
                    title=e["title"],
                    measurements=e.get("measurements", {}),
                    freshness_seconds=e.get("freshnessSeconds", 0),
                    evidence_ids=e.get("evidenceIds", []),
                    offset_seconds=offset,
                    metadata=e.get("metadata", {}),
                )
            )
        return out

    def evidence(self) -> list[Evidence]:
        out: list[Evidence] = []
        for ev in _raw()["evidence"]:
            observed = _dt(ev["observedAtOffsetSeconds"])
            received = _dt(ev["receivedAtOffsetSeconds"])
            out.append(
                Evidence(
                    evidence_id=ev["evidenceId"],
                    source_system=ev["sourceSystem"],
                    source_record_id=ev["sourceRecordId"],
                    observed_at=observed,
                    received_at=received,
                    freshness_seconds=ev["freshnessSeconds"],
                    reliability=ev["reliability"],
                    data_classification=DataClassification(ev.get("dataClassification", "INTERNAL")),
                    summary=ev["summary"],
                    stale=ev.get("stale", False),
                    conflicts_with=ev.get("conflictsWith", []),
                )
            )
        return out


def default_source() -> FixtureSource:
    return FixtureSource()
