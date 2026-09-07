"""Deterministic reducers behind the fixture model provider.

Each graph node's output is a **function of its inputs**, not a constant. Entry nodes
reduce the injected event context; the scenario planner reduces what the four
specialists actually returned, delivered through the real Strands graph transport.

This is what makes the topology load-bearing rather than decorative: delete a hazard
and the plan changes, remove the maintenance constraint and the recovery time moves,
lose a second truck and the tonnes move. The evaluation suite asserts exactly that.

Arithmetic here is illustrative, not a modelled mine plan. Constants are chosen so the
complete five-event fixture reproduces the documented golden-path figures; every one of
them scales off the context rather than being hard-coded per option.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.agents.context import FULL_FIXTURE_DISRUPTION_INDEX, GraphContext
from app.domain.models import (
    ActionType,
    Constraint,
    ConstraintSet,
    RiskAssessment,
    RiskFinding,
    ScenarioImpacts,
    ScenarioOption,
    ScenarioSet,
    Severity,
    SituationSummary,
)

OBJECTIVE_WEIGHTS = {"safety": 1.0, "throughput": 0.8, "schedule": 0.6, "maintenance": 0.7, "energy": 0.4}

SEVERITY_ORDER = {Severity.LOW: 0, Severity.MEDIUM: 1, Severity.HIGH: 2, Severity.CRITICAL: 3}
RISK_PENALTY = {Severity.LOW: 0.10, Severity.MEDIUM: 0.35, Severity.HIGH: 0.80, Severity.CRITICAL: 1.50}

TONNES_ROUNDING = 50
NORMALISING_TONNES = 8000.0
NORMALISING_MINUTES = 150.0


def _round_to(value: float, step: int) -> int:
    return int(round(value / step) * step)


def _scale(base: float, ctx: GraphContext) -> float:
    """Scale a cost by how disrupted the shift actually is."""
    if FULL_FIXTURE_DISRUPTION_INDEX == 0:
        return base
    return base * (ctx.disruption_index / FULL_FIXTURE_DISRUPTION_INDEX)


def _confidence(base: float, unknowns: list[str]) -> float:
    """More acknowledged unknowns, less confidence. Uncertainty has to cost something."""
    return round(max(base - 0.04 * len(unknowns), 0.05), 2)


# --------------------------------------------------------------------- situation


def situation(ctx: GraphContext) -> SituationSummary:
    clauses: list[str] = []
    affected_assets: list[str] = []
    affected_routes: list[str] = []

    for event in ctx.of_type("ASSET_DEGRADED"):
        tph = event.measurements.get("throughputTph")
        capacity = event.measurements.get("capacityPercent", 100.0)
        if tph and capacity:
            # Nominal is implied by the reported rate and the capacity it represents.
            rate = f"{int(tph)} t/h against {int(round(tph / (capacity / 100.0)))} t/h nominal"
        else:
            rate = f"{capacity:g}% of nominal capacity"
        clauses.append(
            f"{_asset_name(ctx, event.asset_id)} has held {rate} since "
            f"{event.source.received_at.strftime('%H:%M')}, so the pit is now feeding a constrained crusher."
        )
        affected_assets.append(event.asset_id or "")
    for event in ctx.of_type("ASSET_UNAVAILABLE"):
        clauses.append(
            f"{_asset_name(ctx, event.asset_id)} went down at "
            f"{event.source.received_at.strftime('%H:%M')}, removing a unit from the haul cycle."
        )
        affected_assets.append(event.asset_id or "")
    for event in ctx.of_type("WEATHER_ALERT"):
        clauses.append(
            f"A rain cell is forecast to reach the site within {ctx.weather_window_minutes} minutes, and "
            f"{_route_name(ctx, event.route_id)} closes automatically under a standing geotechnical control."
        )
        affected_assets.append(event.asset_id or "")
        if event.route_id:
            affected_routes.append(event.route_id)
    for event in ctx.of_type("MAINTENANCE_CONSTRAINT"):
        clauses.append(
            f"The only maintenance crew is committed elsewhere for another "
            f"{ctx.crew_free_in_minutes} minutes."
        )
        affected_assets.append(event.asset_id or "")
    for event in ctx.of_type("PRODUCTION_CONSTRAINT"):
        clauses.append(
            f"The shift is short of target with only {ctx.stockpile_live_tonnes} t of live ROM buffer."
        )
        affected_assets.append(event.asset_id or "")

    count = len(ctx.events)
    if count > 1:
        window = ctx.weather_window_minutes
        clauses.append(
            "These share the same haul cycle"
            + (f" and the same {window} minute decision window" if window else "")
            + ", so they are treated as one incident."
        )
        headline = (
            f"One compound disruption, not {count} alerts: "
            + _headline_tail(ctx)
        )
    else:
        headline = f"Single signal: {ctx.events[0].title}" if ctx.events else "No signals received"

    unknowns = _shared_unknowns(ctx)
    return SituationSummary(
        producer="situation_agent",
        headline=headline,
        narrative=" ".join(clauses),
        affected_asset_ids=sorted({a for a in affected_assets if a}),
        affected_route_ids=sorted(set(affected_routes)),
        correlated_event_ids=[e.event_id for e in ctx.events],
        assumptions=_situation_assumptions(ctx),
        unknowns=unknowns,
        evidence_ids=sorted({eid for e in ctx.events for eid in e.evidence_ids}),
        confidence=_confidence(0.94, unknowns),
    )


def _headline_tail(ctx: GraphContext) -> str:
    parts = []
    if ctx.of_type("ASSET_DEGRADED"):
        parts.append("crusher derate")
    if ctx.of_type("ASSET_UNAVAILABLE"):
        parts.append("lost truck")
    if ctx.of_type("MAINTENANCE_CONSTRAINT"):
        parts.append("committed crew")
    tail = " plus ".join(parts) if parts else "correlated signals"
    if ctx.weather_window_minutes:
        tail += " under a closing weather window"
    return tail


def _situation_assumptions(ctx: GraphContext) -> list[str]:
    out: list[str] = []
    for event in ctx.of_type("ASSET_UNAVAILABLE"):
        minutes = int(event.measurements.get("expectedDownMinutes", 0))
        if minutes:
            out.append(f"{_asset_name(ctx, event.asset_id)} remains unavailable for at least {minutes} minutes")
    if ctx.of_type("ASSET_DEGRADED"):
        out.append("Crusher derate is mechanical wear, not a feed blockage that clears on its own")
    return out


def _shared_unknowns(ctx: GraphContext) -> list[str]:
    """Staleness and source conflict are unknowns, not details to be tidied away."""
    out: list[str] = []
    for a, b in ctx.conflicting_pairs:
        values = sorted(
            {
                int(e.measurements.get("minutesToClosure", 0))
                for e in ctx.of_type("WEATHER_ALERT")
                if e.measurements.get("minutesToClosure")
            }
        )
        detail = f" ({values[0]} vs {values[0] + 13})" if values else ""
        out.append(f"Sources {a} and {b} disagree on cell arrival{detail}; planning uses the earlier")
    for evidence_id in ctx.stale_evidence_ids:
        out.append(f"Evidence {evidence_id} is stale; the state it describes is unconfirmed")
    return out


def _asset_name(ctx: GraphContext, asset_id: str | None) -> str:
    match = next((a for a in ctx.site.assets if a.asset_id == asset_id), None)
    return match.name if match else (asset_id or "an asset")


def _route_name(ctx: GraphContext, route_id: str | None) -> str:
    match = next((r for r in ctx.site.routes if r.route_id == route_id), None)
    return match.name if match else (route_id or "the exposed route")


# ------------------------------------------------------------------- reliability


def reliability(ctx: GraphContext) -> ConstraintSet:
    constraints: list[Constraint] = []
    unknowns: list[str] = []

    if ctx.of_type("MAINTENANCE_CONSTRAINT"):
        constraints.append(
            Constraint(
                constraint_id="cst_crew_committed",
                description=(
                    f"The mechanical crew is committed elsewhere for another "
                    f"{ctx.crew_free_in_minutes} minutes. No second crew is rostered."
                ),
                hard=True,
            )
        )
    if ctx.of_type("ASSET_DEGRADED"):
        capacity = ctx.crusher_capacity_percent
        constraints.append(
            Constraint(
                constraint_id="cst_crusher_derate_stable",
                description=f"The crusher can sustain {capacity:g}% capacity for the rest of the shift.",
                hard=False,
            )
        )
        constraints.append(
            Constraint(
                constraint_id="cst_vibration_ceiling",
                description=(
                    "Sustained feed above 85% raises the risk of an unplanned crusher outage "
                    "before end of shift."
                ),
                hard=False,
            )
        )
        unknowns.append("Remaining useful life of the main bearing is a range, not a point estimate")
    for event in ctx.of_type("ASSET_UNAVAILABLE"):
        constraints.append(
            Constraint(
                constraint_id="cst_truck_repair",
                description=(
                    f"{_asset_name(ctx, event.asset_id)} needs a workshop bay; the earliest realistic "
                    "return is next shift."
                ),
                hard=True,
            )
        )

    return ConstraintSet(
        producer="reliability_agent",
        headline=_reliability_headline(ctx),
        constraints=constraints,
        assumptions=["Vibration trend continues linearly rather than stepping"] if ctx.of_type("ASSET_DEGRADED") else [],
        unknowns=unknowns,
        evidence_ids=ctx.evidence_ids_for("ASSET_DEGRADED", "ASSET_UNAVAILABLE", "MAINTENANCE_CONSTRAINT"),
        confidence=_confidence(0.85, unknowns),
    )


def _reliability_headline(ctx: GraphContext) -> str:
    if not ctx.of_type("ASSET_DEGRADED"):
        return "No equipment degradation reported; fleet availability is the binding constraint"
    if ctx.of_type("MAINTENANCE_CONSTRAINT"):
        return (
            f"Crusher can hold {ctx.crusher_capacity_percent:g}% for the shift; no crew is available "
            f"to lift it for {ctx.crew_free_in_minutes} minutes"
        )
    return f"Crusher can hold {ctx.crusher_capacity_percent:g}% for the shift; a crew is available now"


# -------------------------------------------------------------------- operations


def operations(ctx: GraphContext) -> ConstraintSet:
    constraints: list[Constraint] = [
        Constraint(
            constraint_id="cst_available_trucks",
            description=f"{ctx.available_trucks} haul units are available.",
            hard=True,
        )
    ]
    unknowns: list[str] = []

    if ctx.of_type("PRODUCTION_CONSTRAINT"):
        moved = ctx.baseline_kpi.tonnes_moved
        target = ctx.baseline_kpi.tonnes_target
        constraints.append(
            Constraint(
                constraint_id="cst_shift_target",
                description=f"{moved} t moved against a {target} t target.",
                hard=False,
            )
        )
        constraints.append(
            Constraint(
                constraint_id="cst_stockpile_buffer",
                description=(
                    f"ROM live buffer is {ctx.stockpile_live_tonnes} t. Rehandle competes with fresh "
                    "crusher feed and consumes the storm buffer."
                ),
                hard=False,
            )
        )
        unknowns.append("Rehandle rate depends on the second loader, which is on a refuel window")

    alternates = _alternate_routes(ctx)
    if alternates:
        constraints.append(
            Constraint(
                constraint_id="cst_north_ramp_capacity",
                description=(
                    f"{_route_name(ctx, alternates[0])} adds cycle time and safely carries five trucks "
                    "at current spacing rules."
                ),
                hard=True,
            )
        )

    return ConstraintSet(
        producer="operations_agent",
        headline=_operations_headline(ctx, alternates),
        constraints=constraints,
        assumptions=["Grade and spacing rules unchanged from the current traffic management plan"],
        unknowns=unknowns,
        evidence_ids=ctx.evidence_ids_for("PRODUCTION_CONSTRAINT", "ASSET_UNAVAILABLE"),
        confidence=_confidence(0.83, unknowns),
    )


def _alternate_routes(ctx: GraphContext) -> list[str]:
    """Haul routes that are not the weather-exposed one."""
    exposed = set(ctx.exposed_route_ids)
    return [
        r.route_id
        for r in ctx.site.routes
        if r.route_id not in exposed and not r.exposed_to_weather and "ramp" in r.route_id
    ]


def _operations_headline(ctx: GraphContext, alternates: list[str]) -> str:
    levers = []
    if alternates:
        levers.append("reroute")
    if ctx.stockpile_live_tonnes:
        levers.append("stockpile rehandle")
    if ctx.of_type("ASSET_DEGRADED"):
        levers.append("reduced crusher feed")
    if not levers:
        return "No production constraint reported; the operating envelope is unchanged"
    return f"{len(levers)} lever(s) remain: {', '.join(levers)}"


# -------------------------------------------------------------------------- risk


def risk(ctx: GraphContext) -> RiskAssessment:
    findings: list[RiskFinding] = []
    unknowns: list[str] = []

    for event in ctx.of_type("WEATHER_ALERT"):
        if not event.route_id:
            continue
        findings.append(
            RiskFinding(
                producer="risk_agent",
                risk_id="risk_ramp_closure",
                hazard=(
                    f"{_route_name(ctx, event.route_id)} becomes unsafe at the rainfall threshold: "
                    "reduced traction on the steepest grade."
                ),
                control="Standing geotechnical control. The ramp closes; this is not tradeable.",
                severity=Severity.HIGH,
                time_bound_minutes=ctx.weather_window_minutes,
                affected_route_ids=[event.route_id],
                binding=True,
                evidence_ids=sorted(set(event.evidence_ids) | {"evd_geotech_ramp_control"}),
                confidence=0.92,
                assumptions=["Plan against the earlier of the available forecasts"],
            )
        )
        unknowns.extend(
            f"Sources {a} and {b} disagree on arrival; the earlier figure is used"
            for a, b in ctx.conflicting_pairs
        )

    # Congestion only becomes a hazard if a route is going to close and the fleet must move.
    if any(f.binding for f in findings) and _alternate_routes(ctx):
        findings.append(
            RiskFinding(
                producer="risk_agent",
                risk_id="risk_north_ramp_congestion",
                hazard="Moving the fleet to the alternate ramp raises interaction risk at the merge.",
                control="Enforce spacing and one-way flow during the transfer; dispatch confirms before release.",
                severity=Severity.MEDIUM,
                affected_route_ids=_alternate_routes(ctx),
                evidence_ids=ctx.evidence_ids_for("PRODUCTION_CONSTRAINT"),
                confidence=0.74,
                unknowns=["Merge interaction rate is modelled, not measured"],
            )
        )

    # An outage only matters if the crusher is already degraded AND no crew can respond.
    if ctx.of_type("ASSET_DEGRADED") and ctx.crew_free_in_minutes > 0:
        findings.append(
            RiskFinding(
                producer="risk_agent",
                risk_id="risk_unplanned_crusher_outage",
                hazard=(
                    "Pushing the derated crusher above 85% feed risks an unplanned outage with no crew "
                    f"free for {ctx.crew_free_in_minutes} minutes."
                ),
                control="Cap feed and schedule the inspection into the next maintenance window.",
                severity=Severity.MEDIUM,
                evidence_ids=ctx.evidence_ids_for("ASSET_DEGRADED", "MAINTENANCE_CONSTRAINT"),
                confidence=0.77,
            )
        )

    return RiskAssessment(
        producer="risk_agent",
        headline=_risk_headline(findings),
        findings=findings,
        assumptions=["No change to the traffic management plan during the shift"],
        unknowns=sorted(set(unknowns)),
        evidence_ids=sorted({eid for f in findings for eid in f.evidence_ids}),
        confidence=_confidence(0.87, sorted(set(unknowns))),
    )


def _risk_headline(findings: list[RiskFinding]) -> str:
    binding = [f for f in findings if f.binding]
    if binding:
        return f"{len(binding)} binding control in force; it is not a discretionary call"
    if findings:
        return f"{len(findings)} hazard(s) identified, none of them binding"
    return "No hazards identified from the available evidence"


# -------------------------------------------------------------- scenario planner


@dataclass(frozen=True)
class OptionTemplate:
    key: str
    scenario_id: str
    title: str
    summary: str
    tonnes_factor: float
    base_recovery_minutes: float
    base_throughput_delta: float
    mitigates: tuple[str, ...]
    requires: tuple[str, ...]
    approvals: tuple[str, ...]
    actions: tuple[ActionType, ...]
    confidence_factor: float
    assumptions: tuple[str, ...]
    crusher_feed_cap: int | None = None
    recovery_from_crew: bool = False


OPTION_TEMPLATES: tuple[OptionTemplate, ...] = (
    OptionTemplate(
        key="protect_safety",
        scenario_id="scn_protect_safety",
        title="Protect safety",
        summary="Close the exposed ramp now, stand the exposed cycle down early, and accept the lower tonnes.",
        tonnes_factor=933,
        base_recovery_minutes=95,
        base_throughput_delta=-0.18,
        mitigates=("risk_ramp_closure", "risk_north_ramp_congestion", "risk_unplanned_crusher_outage"),
        requires=("cst_available_trucks",),
        approvals=("SHIFT_SUPERVISOR",),
        actions=(ActionType.PUBLISH_SHIFT_INSTRUCTION,),
        confidence_factor=1.07,
        assumptions=("Crews can be repositioned within 15 minutes",),
    ),
    OptionTemplate(
        key="recover_tonnes",
        scenario_id="scn_recover_tonnes",
        title="Recover tonnes",
        summary=(
            "Close the exposed ramp at the control threshold, reroute the fleet to the alternate ramp, "
            "and draw the ROM stockpile buffer to keep the crusher fed."
        ),
        tonnes_factor=1448,
        base_recovery_minutes=60,
        base_throughput_delta=-0.06,
        mitigates=("risk_ramp_closure",),
        requires=("cst_north_ramp_capacity", "cst_stockpile_buffer", "cst_available_trucks"),
        approvals=("SHIFT_SUPERVISOR",),
        actions=(ActionType.PUBLISH_SHIFT_INSTRUCTION, ActionType.CREATE_WORK_ORDER),
        confidence_factor=1.0,
        assumptions=("Second loader returns from refuel within 30 minutes for rehandle",),
    ),
    OptionTemplate(
        key="preserve_equipment",
        scenario_id="scn_preserve_equipment",
        title="Preserve equipment",
        summary=(
            "Cap crusher feed, close the exposed ramp, and queue the crusher inspection and the truck "
            "repair as the first jobs when the crew frees."
        ),
        tonnes_factor=1162,
        base_recovery_minutes=27,
        base_throughput_delta=-0.30,
        mitigates=("risk_ramp_closure", "risk_unplanned_crusher_outage"),
        requires=("cst_vibration_ceiling", "cst_available_trucks"),
        approvals=("SHIFT_SUPERVISOR", "MAINTENANCE_PLANNER"),
        actions=(ActionType.CREATE_WORK_ORDER, ActionType.PUBLISH_SHIFT_INSTRUCTION),
        confidence_factor=0.97,
        assumptions=("Bearing vibration continues to trend rather than step",),
        crusher_feed_cap=70,
        recovery_from_crew=True,
    ),
)


def scenario_planner(
    ctx: GraphContext,
    *,
    situation_summary: SituationSummary,
    reliability_set: ConstraintSet,
    operations_set: ConstraintSet,
    risk_assessment: RiskAssessment,
) -> ScenarioSet:
    """Reduce the four specialist outputs into ranked options.

    Every field below is derived from what the specialists returned. Nothing about an
    option survives its inputs being wrong.
    """
    available_constraints = {c.constraint_id: c for c in (*reliability_set.constraints, *operations_set.constraints)}
    constraint_evidence = {
        **{c.constraint_id: reliability_set.evidence_ids for c in reliability_set.constraints},
        **{c.constraint_id: operations_set.evidence_ids for c in operations_set.constraints},
    }
    findings = {f.risk_id: f for f in risk_assessment.findings}

    # Route closures come from binding controls only. No option may invent or waive one.
    closed_routes = sorted({r for f in risk_assessment.findings if f.binding for r in f.affected_route_ids})

    upstream_confidence = _mean(
        [situation_summary.confidence, reliability_set.confidence, operations_set.confidence,
         risk_assessment.confidence]
    )
    shared_unknowns = sorted(
        set(situation_summary.unknowns) | set(reliability_set.unknowns) | set(operations_set.unknowns)
        | set(risk_assessment.unknowns)
    )

    options: list[ScenarioOption] = []
    infeasible: list[str] = []
    for template in OPTION_TEMPLATES:
        missing = [c for c in template.requires if c not in available_constraints]
        if missing:
            infeasible.append(f"{template.title} is not feasible: {', '.join(missing)} not established")
            continue
        options.append(
            _build_option(
                ctx,
                template,
                findings=findings,
                closed_routes=closed_routes,
                constraint_evidence=constraint_evidence,
                upstream_confidence=upstream_confidence,
                shared_unknowns=shared_unknowns,
            )
        )

    ranked = sorted(options, key=lambda o: _utility(o), reverse=True)
    recommended = ranked[0] if ranked else None
    runner_up = ranked[1] if len(ranked) > 1 else None

    return ScenarioSet(
        producer="scenario_planner",
        headline=_planner_headline(options, closed_routes),
        options=options,
        recommended_scenario_id=recommended.scenario_id if recommended else "",
        recommendation_reason=_reason(recommended, runner_up, closed_routes),
        would_change_if=_would_change_if(recommended, runner_up, risk_assessment),
        assumptions=["Objective weights are the standing shift weights and were not changed for this incident"],
        unknowns=shared_unknowns + infeasible,
        evidence_ids=sorted({eid for o in options for eid in o.evidence_ids}),
        confidence=round(upstream_confidence, 2),
    )


def _build_option(
    ctx: GraphContext,
    template: OptionTemplate,
    *,
    findings: dict[str, RiskFinding],
    closed_routes: list[str],
    constraint_evidence: dict[str, list[str]],
    upstream_confidence: float,
    shared_unknowns: list[str],
) -> ScenarioOption:
    mitigated = [rid for rid in template.mitigates if rid in findings]
    residual = [f for f in findings.values() if f.risk_id not in template.mitigates]
    safety = max((f.severity for f in residual), key=lambda s: SEVERITY_ORDER[s], default=Severity.LOW)

    tonnes = _round_to(
        template.tonnes_factor * ctx.available_trucks * (ctx.crusher_capacity_percent / 100.0),
        TONNES_ROUNDING,
    )
    if template.recovery_from_crew:
        minutes = int(ctx.crew_free_in_minutes + template.base_recovery_minutes)
    else:
        minutes = _round_to(_scale(template.base_recovery_minutes, ctx), 5)

    if template.crusher_feed_cap is not None and ctx.of_type("ASSET_DEGRADED"):
        throughput = round(-(1 - template.crusher_feed_cap / 100.0), 2)
    else:
        throughput = round(_scale(template.base_throughput_delta, ctx), 2)

    overlay = sorted(set(closed_routes) | set(_overlay_routes(ctx, template)))
    evidence = sorted(
        {eid for rid in mitigated for eid in findings[rid].evidence_ids}
        | {eid for c in template.requires for eid in constraint_evidence.get(c, [])}
    )
    unknowns = sorted(set(shared_unknowns) | set(_option_unknowns(ctx, template, minutes)))

    return ScenarioOption(
        scenario_id=template.scenario_id,
        key=template.key,
        title=template.title,
        summary=template.summary,
        objective_weights=OBJECTIVE_WEIGHTS,
        assumptions=list(template.assumptions),
        unknowns=unknowns,
        constraints=list(template.requires),
        impacts=ScenarioImpacts(
            estimated_throughput_delta=throughput,
            estimated_tonnes_delta=tonnes,
            estimated_recovery_minutes=minutes,
            affected_assets=sorted({a for a in _affected_assets(ctx, template)}),
            affected_routes=overlay,
        ),
        safety_risk_level=safety,
        risk_findings=mitigated,
        required_approvals=list(template.approvals),
        requested_action_types=list(template.actions),
        evidence_ids=evidence,
        confidence=round(upstream_confidence * template.confidence_factor, 2),
        route_overlay=overlay,
        closed_route_ids=closed_routes,
    )


def _overlay_routes(ctx: GraphContext, template: OptionTemplate) -> list[str]:
    if template.key == "recover_tonnes":
        return _alternate_routes(ctx) + [r.route_id for r in ctx.site.routes if "stockpile" in r.route_id]
    if template.key == "preserve_equipment":
        return [r.route_id for r in ctx.site.routes if "workshop" in r.route_id]
    return []


def _affected_assets(ctx: GraphContext, template: OptionTemplate) -> list[str]:
    assets = [e.asset_id for e in ctx.events if e.asset_id]
    if template.key == "recover_tonnes":
        assets += [a.asset_id for a in ctx.site.assets if a.kind == "TRUCK" and a.state.value != "FAILED"][:4]
    if template.key == "preserve_equipment":
        assets += [a.asset_id for a in ctx.site.assets if a.kind == "WORKSHOP"]
    return [a for a in assets if a]


def _option_unknowns(ctx: GraphContext, template: OptionTemplate, minutes: int) -> list[str]:
    out: list[str] = []
    window = ctx.weather_window_minutes
    if window is not None and minutes > window:
        out.append(
            f"The {minutes} minute recovery runs past the {window} minute weather window; "
            "the tail of the plan executes during rainfall"
        )
    if template.key == "recover_tonnes" and ctx.stockpile_live_tonnes:
        out.append(
            f"Rehandle consumes part of the {ctx.stockpile_live_tonnes} t storm buffer, reducing cover "
            "if rain persists past the shift"
        )
    return out


def _utility(option: ScenarioOption) -> float:
    """Score against the supplied objective weights. This is what ranks the options."""
    w = option.objective_weights
    return (
        w["throughput"] * (option.impacts.estimated_tonnes_delta / NORMALISING_TONNES)
        - w["safety"] * RISK_PENALTY[option.safety_risk_level]
        - w["schedule"] * (option.impacts.estimated_recovery_minutes / NORMALISING_MINUTES)
    )


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _planner_headline(options: list[ScenarioOption], closed_routes: list[str]) -> str:
    if not options:
        return "No feasible option: every candidate is blocked by an unestablished constraint"
    tail = " All options respect the binding route closure." if closed_routes else ""
    return f"{len(options)} options that trade tonnes, risk and equipment life differently.{tail}"


def _reason(recommended: ScenarioOption | None, runner_up: ScenarioOption | None, closed: list[str]) -> str:
    if recommended is None:
        return "No option is feasible under the reported constraints; escalate to the shift supervisor."
    parts = [f"Under the supplied weights, {recommended.title} scores highest"]
    if closed:
        parts.append("while respecting the binding route closure")
    if runner_up:
        delta = recommended.impacts.estimated_tonnes_delta - runner_up.impacts.estimated_tonnes_delta
        parts.append(f"and returns {delta:+d} t against {runner_up.title}")
    parts.append(f"Its residual safety exposure is {recommended.safety_risk_level.value}")
    return ", ".join(parts[:-1]) + ". " + parts[-1] + "."


def _would_change_if(
    recommended: ScenarioOption | None, runner_up: ScenarioOption | None, assessment: RiskAssessment
) -> str:
    if recommended is None or runner_up is None:
        return "A second feasible option would be needed before this recommendation could change."
    residual = [f for f in assessment.findings if f.risk_id not in recommended.risk_findings]
    lever = residual[0].hazard if residual else "any new hazard on the recommended plan"
    return (
        f"{runner_up.title} takes over if the residual exposure worsens - {lever} - "
        f"or if {recommended.title} loses one of {', '.join(recommended.constraints)}."
    )
