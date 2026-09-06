"""Deterministic specialist findings for the compound-disruption fixture.

These are the payloads FixtureModel returns at each agent boundary. They are written
here, in typed form, rather than generated, so the demo replays identically and the
evaluation suite has a fixed expectation to assert against.

In Bedrock mode these are replaced by real model output validated against the same
schemas; nothing downstream changes.
"""

from __future__ import annotations

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


def situation_summary() -> SituationSummary:
    return SituationSummary(
        producer="situation_agent",
        headline="One compound disruption, not four alerts: crusher derate plus lost truck under a closing weather window",
        narrative=(
            "Primary Crusher 01 has held 1800 t/h against 2400 t/h nominal since 14:03, so the pit is now "
            "feeding a constrained crusher. Truck 204 keyed off at Bench 2 at 14:08, removing one of four "
            "units on the East Ramp cycle. A rain cell is forecast to reach North Pit within 42 minutes, and "
            "the East Ramp closes automatically at 10 mm accumulated rainfall under a standing geotechnical "
            "control. These share the same haul cycle and the same 42 minute decision window, so they are "
            "treated as one incident."
        ),
        affected_asset_ids=[
            "asset_primary_crusher_01",
            "asset_truck_204",
            "asset_rom_stockpile_01",
            "asset_weather_cell_01",
        ],
        affected_route_ids=["route_east_ramp"],
        correlated_event_ids=[
            "evt_crusher_derate",
            "evt_truck_204_unavailable",
            "evt_weather_route_closure",
            "evt_maintenance_crew_committed",
            "evt_production_constraint",
        ],
        assumptions=[
            "Truck 204 remains unavailable for at least 90 minutes",
            "Crusher derate is mechanical wear, not a feed blockage that clears on its own",
        ],
        unknowns=[
            "Regional forecast and on-site gauge disagree on cell arrival by 13 minutes (42 vs 55)",
            "Truck 204 telemetry is 15 minutes stale; payload state at shutdown is unconfirmed",
        ],
        evidence_ids=[
            "evd_plant_scada_derate",
            "evd_fleet_dispatch_204",
            "evd_weather_bom",
            "evd_weather_onsite",
            "evd_production_ledger",
        ],
        confidence=0.86,
    )


def reliability_constraints() -> ConstraintSet:
    return ConstraintSet(
        producer="reliability_agent",
        headline="Crusher can hold 75% for the shift; no crew is available to lift it before 16:10",
        constraints=[
            Constraint(
                constraint_id="cst_crew_committed",
                description="Mechanical crew A is committed to the Shovel 02 gearbox until 16:10. No second crew is rostered.",
                hard=True,
            ),
            Constraint(
                constraint_id="cst_crusher_derate_stable",
                description="Crusher can sustain 75% capacity for the remainder of the shift; bearing vibration is trending up but below alarm.",
                hard=False,
            ),
            Constraint(
                constraint_id="cst_truck_204_repair",
                description="Truck 204 hydraulic fault H-221 needs a workshop bay; earliest realistic return is next shift.",
                hard=True,
            ),
            Constraint(
                constraint_id="cst_vibration_ceiling",
                description="Sustained feed above 85% raises the risk of an unplanned crusher outage before end of shift.",
                hard=False,
            ),
        ],
        assumptions=["Vibration trend continues linearly rather than stepping"],
        unknowns=["Remaining useful life of the main bearing is a range of 40-120 operating hours, not a point estimate"],
        evidence_ids=["evd_crusher_vibration", "evd_cmms_crew_roster", "evd_fleet_dispatch_204"],
        confidence=0.81,
    )


def operations_envelope() -> ConstraintSet:
    return ConstraintSet(
        producer="operations_agent",
        headline="Three levers remain: North Ramp reroute, ROM stockpile rehandle, and reduced crusher feed",
        constraints=[
            Constraint(
                constraint_id="cst_shift_target",
                description="8200 t moved against a 12000 t target. Do-nothing projection is 10400 t, a 1600 t shortfall.",
                hard=False,
            ),
            Constraint(
                constraint_id="cst_stockpile_buffer",
                description="ROM live buffer is 6200 t. Rehandle competes with fresh crusher feed and consumes the storm buffer.",
                hard=False,
            ),
            Constraint(
                constraint_id="cst_north_ramp_capacity",
                description="North Ramp adds 4 minutes per cycle and safely carries 5 trucks with current spacing rules.",
                hard=True,
            ),
            Constraint(
                constraint_id="cst_seven_trucks",
                description="Seven haul units are available with Truck 204 out.",
                hard=True,
            ),
        ],
        assumptions=["North Ramp grade and spacing rules unchanged from the current traffic management plan"],
        unknowns=["Rehandle rate depends on the second loader, which is on a 30 minute refuel window"],
        evidence_ids=["evd_production_ledger", "evd_fleet_dispatch_204"],
        confidence=0.79,
    )


def risk_assessment() -> RiskAssessment:
    return RiskAssessment(
        producer="risk_agent",
        headline="East Ramp closure is a binding standing control, not a discretionary call",
        findings=[
            RiskFinding(
                producer="risk_agent",
                risk_id="risk_ramp_closure",
                hazard="East Ramp becomes unsafe at 10 mm accumulated rainfall: reduced traction on the steepest grade.",
                control="Standing geotechnical control std-ramp-closure-v4. The ramp closes; this is not tradeable.",
                severity=Severity.HIGH,
                time_bound_minutes=42,
                affected_route_ids=["route_east_ramp"],
                evidence_ids=["evd_geotech_ramp_control", "evd_weather_bom"],
                confidence=0.92,
                assumptions=["Plan against the earlier of the two forecasts"],
                unknowns=["On-site gauge puts arrival 13 minutes later; the earlier figure is used"],
            ),
            RiskFinding(
                producer="risk_agent",
                risk_id="risk_north_ramp_congestion",
                hazard="Moving the full fleet to North Ramp raises interaction risk at the merge with the workshop spur.",
                control="Enforce 60 m spacing and one-way flow during the transfer; dispatch confirms before release.",
                severity=Severity.MEDIUM,
                affected_route_ids=["route_north_ramp", "route_workshop_spur"],
                evidence_ids=["evd_production_ledger"],
                confidence=0.74,
                unknowns=["Merge point interaction rate is modelled, not measured"],
            ),
            RiskFinding(
                producer="risk_agent",
                risk_id="risk_unplanned_crusher_outage",
                hazard="Pushing the derated crusher above 85% feed risks an unplanned outage with no crew to respond.",
                control="Cap feed and schedule the inspection into the next maintenance window.",
                severity=Severity.MEDIUM,
                evidence_ids=["evd_crusher_vibration", "evd_cmms_crew_roster"],
                confidence=0.77,
            ),
        ],
        assumptions=["No change to the traffic management plan during the shift"],
        unknowns=["Two weather sources disagree; the earlier arrival is used for planning"],
        evidence_ids=["evd_geotech_ramp_control", "evd_weather_bom", "evd_weather_onsite", "evd_crusher_vibration"],
        confidence=0.83,
    )


def _protect_safety() -> ScenarioOption:
    return ScenarioOption(
        scenario_id="scn_protect_safety",
        key="protect_safety",
        title="Protect safety",
        summary="Close the East Ramp now, stand the exposed cycle down early, and accept the lower tonnes.",
        objective_weights=OBJECTIVE_WEIGHTS,
        assumptions=[
            "Cell arrives at the earlier forecast of 42 minutes",
            "Crews can be repositioned within 15 minutes",
        ],
        unknowns=["If the cell tracks 13 minutes later, roughly 400 t of this loss was avoidable"],
        constraints=["cst_seven_trucks", "cst_crew_committed", "cst_north_ramp_capacity"],
        impacts=ScenarioImpacts(
            estimated_throughput_delta=-0.18,
            estimated_tonnes_delta=1300,
            estimated_recovery_minutes=95,
            affected_assets=["asset_primary_crusher_01", "asset_truck_204", "asset_weather_cell_01"],
            affected_routes=["route_east_ramp"],
        ),
        safety_risk_level=Severity.LOW,
        risk_findings=["risk_ramp_closure"],
        required_approvals=["SHIFT_BOSS"],
        requested_action_types=[ActionType.PUBLISH_SHIFT_INSTRUCTION],
        evidence_ids=["evd_geotech_ramp_control", "evd_weather_bom", "evd_production_ledger"],
        confidence=0.88,
        route_overlay=["route_east_ramp"],
        closed_route_ids=["route_east_ramp"],
    )


def _recover_tonnes() -> ScenarioOption:
    return ScenarioOption(
        scenario_id="scn_recover_tonnes",
        key="recover_tonnes",
        title="Recover tonnes",
        summary="Close the East Ramp at the control threshold, reroute the fleet to the North Ramp, and draw the ROM stockpile buffer to keep the crusher fed.",
        objective_weights=OBJECTIVE_WEIGHTS,
        assumptions=[
            "North Ramp carries five trucks at 60 m spacing",
            "Second loader returns from refuel within 30 minutes for rehandle",
        ],
        unknowns=[
            "Rehandle consumes 1800 t of the 6200 t storm buffer, reducing cover if rain persists past the shift",
            "60 minute recovery runs past the 42 minute weather window; the tail of the plan executes during rainfall on the sheltered ramp",
        ],
        constraints=["cst_north_ramp_capacity", "cst_stockpile_buffer", "cst_seven_trucks", "cst_vibration_ceiling"],
        impacts=ScenarioImpacts(
            estimated_throughput_delta=-0.06,
            estimated_tonnes_delta=2900,
            estimated_recovery_minutes=60,
            affected_assets=[
                "asset_primary_crusher_01",
                "asset_rom_stockpile_01",
                "asset_truck_204",
                "asset_truck_205",
                "asset_truck_206",
                "asset_truck_207",
            ],
            affected_routes=["route_east_ramp", "route_north_ramp", "route_stockpile_link"],
        ),
        safety_risk_level=Severity.MEDIUM,
        risk_findings=["risk_ramp_closure", "risk_north_ramp_congestion"],
        required_approvals=["SHIFT_BOSS"],
        requested_action_types=[ActionType.PUBLISH_SHIFT_INSTRUCTION, ActionType.CREATE_WORK_ORDER],
        evidence_ids=[
            "evd_geotech_ramp_control",
            "evd_weather_bom",
            "evd_weather_onsite",
            "evd_production_ledger",
            "evd_fleet_dispatch_204",
        ],
        confidence=0.82,
        route_overlay=["route_north_ramp", "route_stockpile_link", "route_east_ramp"],
        closed_route_ids=["route_east_ramp"],
    )


def _preserve_equipment() -> ScenarioOption:
    return ScenarioOption(
        scenario_id="scn_preserve_equipment",
        key="preserve_equipment",
        title="Preserve equipment",
        summary="Cap crusher feed at 70%, close the East Ramp, and queue the crusher inspection and Truck 204 repair as the first jobs when the crew frees at 16:10.",
        objective_weights=OBJECTIVE_WEIGHTS,
        assumptions=[
            "Bearing vibration continues to trend rather than step",
            "Crew A frees at 16:10 as rostered",
        ],
        unknowns=["Whether capping feed actually prevents the outage or only delays it into the next shift"],
        constraints=["cst_crew_committed", "cst_vibration_ceiling", "cst_truck_204_repair", "cst_seven_trucks"],
        impacts=ScenarioImpacts(
            estimated_throughput_delta=-0.30,
            estimated_tonnes_delta=1900,
            estimated_recovery_minutes=140,
            affected_assets=["asset_primary_crusher_01", "asset_workshop_01", "asset_truck_204"],
            affected_routes=["route_east_ramp", "route_workshop_spur"],
        ),
        safety_risk_level=Severity.MEDIUM,
        risk_findings=["risk_unplanned_crusher_outage", "risk_ramp_closure"],
        required_approvals=["SHIFT_BOSS", "MAINTENANCE_PLANNER"],
        requested_action_types=[ActionType.CREATE_WORK_ORDER, ActionType.PUBLISH_SHIFT_INSTRUCTION],
        evidence_ids=["evd_crusher_vibration", "evd_cmms_crew_roster", "evd_geotech_ramp_control"],
        confidence=0.8,
        route_overlay=["route_workshop_spur", "route_east_ramp"],
        closed_route_ids=["route_east_ramp"],
    )


def scenario_set() -> ScenarioSet:
    return ScenarioSet(
        producer="scenario_planner",
        headline="Three options that trade tonnes, risk and equipment life differently. All three respect the ramp closure control.",
        options=[_protect_safety(), _recover_tonnes(), _preserve_equipment()],
        recommended_scenario_id="scn_recover_tonnes",
        recommendation_reason=(
            "Under the supplied weights, Recover tonnes satisfies the binding ramp-closure control while "
            "returning 1600 t more than Protect safety. Its residual risk is North Ramp congestion, which has "
            "an established spacing control, rather than an unmanaged hazard."
        ),
        would_change_if=(
            "Protect safety wins if the on-site gauge is correct and the cell arrives 13 minutes later than "
            "planned but with higher intensity, or if the second loader does not return from refuel in time. "
            "Preserve equipment wins if bearing vibration steps rather than trends before 16:10."
        ),
        assumptions=["Objective weights are the standing shift weights and were not changed for this incident"],
        unknowns=["Two weather sources disagree by 13 minutes; planning uses the earlier"],
        evidence_ids=[
            "evd_geotech_ramp_control",
            "evd_weather_bom",
            "evd_weather_onsite",
            "evd_production_ledger",
            "evd_crusher_vibration",
            "evd_cmms_crew_roster",
        ],
        confidence=0.84,
    )
