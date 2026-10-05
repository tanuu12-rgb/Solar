"""Page 4: Deterministic Regulatory Feasibility Screening.

Screens candidate feeder solarization scenarios against regulatory and technical rules
from PM-KUSUM guidelines and MSEDCL circulars. No ML or heuristic algorithms.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is in sys.path for robust imports from core
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
import streamlit as st

from core.errors import MissingInputError
from app.state import (
    get_scenario_inputs,
    save_scenario_inputs,
    get_illustrative_scenario_inputs,
    get_cached_feeder_schedule,
    run_cached_demand,
    run_cached_solar,
    run_cached_dispatch,
    render_disclaimer_footer,
    render_scenario_banner,
)
from core.feasibility.rules_engine import evaluate_feasibility_rules, select_transmission_voltage
from core.feasibility.explanations import generate_feasibility_verdict
from core.config_loader import get_assumption_value
from app.theme import apply_theme

def render_missing_input_card(error: object) -> None:
    key_name = getattr(error, "key", "Scenario Input")
    msg = getattr(error, "message", str(error)) or "This engineering stage requires specific feeder parameters that have not been configured yet."
    st.warning(
        f"⚠️ **Feeder Configuration Required:** `{key_name}`\n\n"
        f"{msg}\n\n"
        "Per **PROJECT_SPEC Section 0 Rule 1 & Rule 3 (Input Honesty)**, the system does not inject silent synthetic defaults. "
        "You can configure custom parameters on **Page 1: Inputs & Data**, or immediately load an illustrative case study for demonstration."
    )
    col1, col2 = st.columns([1, 2])
    with col1:
        if st.button("✨ Load Illustrative Scenario (Bhatangali Demo)", type="primary", key=f"btn_load_demo_{key_name}"):
            save_scenario_inputs(get_illustrative_scenario_inputs())
            st.rerun()

from app.theme import apply_theme, render_urja_header

st.set_page_config(page_title="ऊर्जाSetu - Feasibility Screening", page_icon="⚖️", layout="wide")
apply_theme()

render_urja_header(
    title="Deterministic Feasibility Screening",
    subtitle="3-tier statutory screening against MSEDCL circulars, land constraints, PT capacity, and voltage guidelines.",
    badge_label="Step 4 of 6 • Regulatory Screening",
    icon="⚖️",
)

try:
    inputs = get_scenario_inputs()
    render_scenario_banner(inputs.is_illustrative, inputs.feeder_name)

    if inputs.available_land_acres is None or inputs.available_land_acres <= 0:
        raise MissingInputError(
            "available_land_acres",
            "Available land (acres) not configured. Please enter available land on Page 1 or click 'Load illustrative scenario'.",
        )
    if inputs.distance_to_substation_km is None or inputs.distance_to_substation_km <= 0:
        raise MissingInputError(
            "distance_to_substation_km",
            "Distance to substation (km) not configured. Please enter distance on Page 1 or click 'Load illustrative scenario'.",
        )

    schedule_df = get_cached_feeder_schedule()
    feeder_rows = schedule_df[schedule_df["feeder_name"] == inputs.feeder_name]
    feeder_row = feeder_rows.iloc[0] if not feeder_rows.empty else schedule_df.iloc[0]

    # Run demand, solar, and dispatch to obtain simulated performance
    crop_mix_tuple = tuple(sorted(inputs.crop_mix_ha.items()))
    irrig_methods_tuple = tuple(sorted(inputs.irrigation_methods.items()))
    daily_water_df, hourly_demand_df = run_cached_demand(
        crop_mix_tuple=crop_mix_tuple,
        irrigation_methods_tuple=irrig_methods_tuple,
        connected_pump_kw=inputs.connected_pump_kw,
        window_start=feeder_row["window_start"],
        window_end=feeder_row["window_end"],
    )
    solar_df = run_cached_solar(solar_capacity_mwp=inputs.candidate_solar_mwp)
    demand_hash_key = f"{inputs.feeder_name}_{inputs.connected_pump_kw}_{sum(inputs.crop_mix_ha.values())}"
    dispatch_df, dispatch_metrics = run_cached_dispatch(
        solar_capacity_mwp=inputs.candidate_solar_mwp,
        battery_capacity_mwh=inputs.candidate_battery_mwh,
        demand_hash_key=demand_hash_key,
        solar_series=solar_df["solar_generation_kwh"],
        demand_series=hourly_demand_df["pump_served_kwh"],
    )

    # Compute parameters to evaluate
    pt_mva = float(feeder_row["pt_capacity_mva"])
    try:
        land_req_per_mw = float(get_assumption_value("land_requirement_acres_per_mw"))
    except Exception:
        land_req_per_mw = float(get_assumption_value("land_requirement_acres_per_mwp"))

    candidate_land_ratio = (
        inputs.available_land_acres / (inputs.candidate_solar_mwp * land_req_per_mw)
        if inputs.available_land_acres is not None and inputs.candidate_solar_mwp
        else 0.0
    )
    transformer_loading_ratio = (
        inputs.candidate_solar_mwp / (pt_mva * 0.95)
        if inputs.candidate_solar_mwp
        else 0.0
    )

    try:
        solar_capex_per_mwp = float(get_assumption_value("solar_capex_per_mwp"))
    except Exception:
        solar_capex_per_mwp = float(get_assumption_value("solar_capex_per_mwp_inr"))

    try:
        battery_capex_per_mwh = float(get_assumption_value("battery_capex_per_mwh"))
    except Exception:
        battery_capex_per_mwh = float(get_assumption_value("battery_capex_per_mwh_inr"))

    batt_mwh = inputs.candidate_battery_mwh or 0.0
    cand_solar = inputs.candidate_solar_mwp or 0.0
    dist_km = inputs.distance_to_substation_km or 0.0

    selected_voltage_kv = select_transmission_voltage(cand_solar, dist_km)
    total_capex = cand_solar * solar_capex_per_mwp + batt_mwh * battery_capex_per_mwh
    budget_surplus = (inputs.budget_inr - total_capex) if inputs.budget_inr is not None else 0.0

    achieved_solar_share = dispatch_metrics["solar_share_percent"] / 100.0
    unmet_demand_fraction = hourly_demand_df["pump_unmet_kwh"].sum() / max(1.0, hourly_demand_df["pump_demand_kwh"].sum())

    measured_params = {
        "solar_plant_mw": cand_solar,
        "distance_to_substation_km": dist_km,
        "candidate_land_ratio": candidate_land_ratio,
        "transformer_loading_ratio": transformer_loading_ratio,
        "window_duration_hours": 8.0,
        "evacuation_voltage_kv": selected_voltage_kv,
        "solar_capex_per_mwp_inr": solar_capex_per_mwp,
        "solar_share_fraction": achieved_solar_share,
        "budget_surplus_inr": budget_surplus,
        "unmet_demand_fraction": unmet_demand_fraction,
    }

    context_vars = {
        "available_land_acres": inputs.available_land_acres,
        "pt_capacity_mva": pt_mva,
    }

    evaluations = evaluate_feasibility_rules(measured_params)
    verdict = generate_feasibility_verdict(evaluations, context_vars, land_requirement_acres_per_mw=land_req_per_mw, pt_capacity_mva=pt_mva)

    # --- Overall Verdict Banner ---
    overall_verdict = verdict["verdict"]
    if overall_verdict == "Feasible":
        st.success(
            f"### Overall Feasibility Verdict: 🟢 FEASIBLE\n\n"
            f"{verdict['summary_statement']}"
        )
    elif overall_verdict == "Marginal":
        st.warning(
            f"### Overall Feasibility Verdict: 🟡 MARGINAL\n\n"
            f"{verdict['summary_statement']}"
        )
    else:
        st.error(
            f"### Overall Feasibility Verdict: 🔴 REJECTED\n\n"
            f"{verdict['summary_statement']}"
        )

    # Top KPI metrics
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Rules Evaluated", verdict["total_rules_evaluated"])
    with c2:
        st.metric("Rules Passed", verdict["rules_passed"])
    with c3:
        st.metric("Blocking Failures", len(verdict["blocking_failures"]))
    with c4:
        st.metric("Warning Flags", len(verdict["warning_failures"]))

    st.markdown("---")

    # --- Ranked Rejection Reasons ---
    if verdict["ranked_rejection_reasons"]:
        st.subheader("⚠️ Ranked Rejection & Advisory Reasons")
        for idx, r in enumerate(verdict["ranked_rejection_reasons"], 1):
            is_blocking = r.get("severity") == "blocking"
            badge = "🔴 BLOCKING REJECTION" if is_blocking else "🟡 OPERATIONAL ADVISORY"
            box_fn = st.error if is_blocking else st.warning
            box_fn(
                f"**#{idx} [{badge}] {r['rule_id']}: {r['description']}**\n\n"
                f"- **Finding:** {r['explanation']}\n"
                f"- **Statutory Threshold:** {r['operator']} {r['threshold']} {r['unit']}\n"
                f"- **Authoritative Source:** {r['source']}"
            )

    # --- Remediation Hints ---
    if verdict["remediation_hints"]:
        st.subheader("💡 Actionable Remediation Guidance (Path to Feasibility)")
        for hint in verdict["remediation_hints"]:
            st.info(f"👉 {hint}")

    st.markdown("---")

    # --- Full Rule Evaluation Matrix ---
    st.subheader("📊 Full Regulatory & Technical Screening Matrix")

    table_records = []
    for r in verdict["rule_table"]:
        status_label = "✅ PASS" if r["passed"] else ("🔴 FAIL" if r["severity"] == "blocking" else "🟡 WARN")
        table_records.append({
            "Status": status_label,
            "Rule ID": r["rule_id"],
            "Description": r["description"],
            "Measured": f"{r['measured_value']:.2f}" if isinstance(r["measured_value"], (int, float)) else str(r["measured_value"]),
            "Operator": r["operator"],
            "Threshold": f"{r['threshold']:.2f}" if isinstance(r["threshold"], (int, float)) else str(r["threshold"]),
            "Unit": r["unit"],
            "Severity": r["severity"].upper(),
            "Finding Explanation": r["explanation"],
            "Source": r["source"],
        })

    st.dataframe(pd.DataFrame(table_records), use_container_width=True)

    render_disclaimer_footer()

except MissingInputError as e:
    render_missing_input_card(e)
    render_disclaimer_footer()
