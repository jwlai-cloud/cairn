"""Read-only tools exposed to the specialist agents.

Tier 0 (docs/architecture/04 4.4). These are the only tools any agent may reach.
Proposal tools and state-changing tools live in separate modules and are never
registered on an Agent, so a read-only specialist cannot reach a write path by
rewording its prompt.

Each tool is bound to one run's GraphContext, so a tool cannot read outside the
site and events the run was given.
"""

from __future__ import annotations

from typing import Any, Callable

from strands import tool

from app.agents.context import GraphContext

# Node allow-lists from docs/architecture/03 3.5. Enforced by the hook chain at call
# time, not by prompt wording.
NODE_TOOLS: dict[str, tuple[str, ...]] = {
    "situation": ("get_site_context", "get_recent_events", "get_asset_status", "get_evidence"),
    "reliability": ("get_asset_status", "get_maintenance_constraints", "get_evidence"),
    "operations": ("get_production_constraints", "get_recent_events", "get_site_context"),
    "risk": ("get_weather_window", "get_site_context", "get_evidence"),
    # The planner reasons over its dependencies' output. It gets no tools at all.
    "scenario_planner": (),
}


def _event_view(event) -> dict[str, Any]:
    return {
        "eventId": event.event_id,
        "eventType": event.event_type.value,
        "assetId": event.asset_id,
        "routeId": event.route_id,
        "severity": event.severity.value,
        "title": event.title,
        "measurements": event.measurements,
        "freshnessSeconds": event.freshness_seconds,
        "evidenceIds": event.evidence_ids,
        "observedAt": event.source.observed_at.isoformat(),
    }


def build_read_tools(ctx: GraphContext) -> dict[str, Callable[..., Any]]:
    """Build this run's read tools. Every result carries provenance."""

    @tool
    def get_site_context() -> dict:
        """Return the site, its assets and its haul routes."""
        return {
            "siteId": ctx.site.site_id,
            "name": ctx.site.name,
            "shiftLabel": ctx.site.shift_label,
            "assets": [
                {"assetId": a.asset_id, "name": a.name, "kind": a.kind, "state": a.state.value}
                for a in ctx.site.assets
            ],
            "routes": [
                {"routeId": r.route_id, "name": r.name, "open": r.open, "exposedToWeather": r.exposed_to_weather}
                for r in ctx.site.routes
            ],
        }

    @tool
    def get_recent_events() -> dict:
        """Return every operational event received on this run."""
        return {"count": len(ctx.events), "events": [_event_view(e) for e in ctx.events]}

    @tool
    def get_asset_status(asset_id: str) -> dict:
        """Return the current state of one asset and the events that touched it."""
        asset = next((a for a in ctx.site.assets if a.asset_id == asset_id), None)
        if asset is None:
            return {"assetId": asset_id, "found": False}
        return {
            "assetId": asset.asset_id,
            "found": True,
            "name": asset.name,
            "kind": asset.kind,
            "state": asset.state.value,
            "capacityPercent": asset.capacity_percent,
            "detail": asset.detail,
            "events": [_event_view(e) for e in ctx.events if e.asset_id == asset_id],
        }

    @tool
    def get_maintenance_constraints() -> dict:
        """Return maintenance and crew constraints for this shift."""
        return {
            "crewFreeInMinutes": ctx.crew_free_in_minutes,
            "events": [_event_view(e) for e in ctx.of_type("MAINTENANCE_CONSTRAINT")],
        }

    @tool
    def get_production_constraints() -> dict:
        """Return production targets, stockpile buffer and fleet availability."""
        return {
            "tonnesMoved": ctx.baseline_kpi.tonnes_moved,
            "tonnesTarget": ctx.baseline_kpi.tonnes_target,
            "stockpileLiveTonnes": ctx.stockpile_live_tonnes,
            "availableTrucks": ctx.available_trucks,
            "crusherCapacityPercent": ctx.crusher_capacity_percent,
            "events": [_event_view(e) for e in ctx.of_type("PRODUCTION_CONSTRAINT")],
        }

    @tool
    def get_weather_window() -> dict:
        """Return the weather window and the routes it exposes."""
        return {
            "minutesToClosure": ctx.weather_window_minutes,
            "exposedRouteIds": list(ctx.exposed_route_ids),
            "events": [_event_view(e) for e in ctx.of_type("WEATHER_ALERT")],
        }

    @tool
    def get_evidence() -> dict:
        """Return the evidence set, including anything stale or in conflict."""
        return {
            "evidence": [
                {
                    "evidenceId": e.evidence_id,
                    "sourceSystem": e.source_system,
                    "summary": e.summary,
                    "freshnessSeconds": e.freshness_seconds,
                    "reliability": e.reliability,
                    "dataClassification": e.data_classification.value,
                    "stale": e.stale,
                    "conflictsWith": e.conflicts_with,
                }
                for e in ctx.evidence
            ],
            "staleCount": len(ctx.stale_evidence_ids),
            "conflictCount": len(ctx.conflicting_pairs),
        }

    built = [
        get_site_context, get_recent_events, get_asset_status, get_maintenance_constraints,
        get_production_constraints, get_weather_window, get_evidence,
    ]
    return {t.tool_name: t for t in built}


def tools_for(node_id: str, registry: dict[str, Callable[..., Any]]) -> list[Callable[..., Any]]:
    return [registry[name] for name in NODE_TOOLS.get(node_id, ()) if name in registry]
