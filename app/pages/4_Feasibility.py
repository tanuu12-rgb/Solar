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
    get_cached_feeder_schedule,
    render_disclaimer_footer,
    render_scenario_banner,
)
from core.feasibility.rules_engine import evaluate_feasibility_rules
from core.feasibility.explanations import generate_feasibility_verdict
from core.config_loader import get_assumption_value

st.set_page_config(page_title="Feasibility Screening - Feeder Solar DSS", page_icon="📋", layout="wide")

try:
    inputs = get_scenario_inputs()
    render_scenario_banner(inputs.is_illustrative)

    st.title("📋 Page 4: Deterministic Regulatory Feasibility Screening")
    st.markdown(
        """
        Evaluates the scenario against statutory rules and grid connection thresholds defined in `config/rules.yaml`.
        This is a **deterministic rule engine** derived from **MSEDCL circulars** and **MNRE PM-KUSUM guidelines**.
        """
    )

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

    # Compute parameters to evaluate
    pt_mva = float(feeder_row["pt_capacity_mva"])
    land_req_per_mw = float(get_assumption_value("land_requirement_acres_per_mwp"))
    candidate_land_ratio = inputs.available_land_acres / (inputs.candidate_solar_mwp * land_req_per_mw)
    transformer_loading_ratio = inputs.candidate_solar_mwp / (pt_mva * 0.95)
    solar_capex_per_mwp = float(get_assumption_value("solar_capex_per_mwp_inr"))

    measured_params = {
        "solar_plant_mw": inputs.candidate_solar_mwp,
        "distance_to_substation_km": inputs.distance_to_substation_km,
        "candidate_land_ratio": candidate_land_ratio,
        "transformer_loading_ratio": transformer_loading_ratio,
        "window_duration_hours": 8.0,
        "evacuation_voltage_kv": 11.0,
        "solar_capex_per_mwp_inr": solar_capex_per_mwp,
    }

    context_vars = {
        "available_land_acres": inputs.available_land_acres,
        "pt_capacity_mva": pt_mva,
    }

    evaluations = evaluate_feasibility_rules(measured_params)
    verdict = generate_feasibility_verdict(evaluations, context_vars)

    # --- Overall Verdict Banner ---
    overall_status = verdict["overall_status"]
    if overall_status == "Feasible":
        st.success(f"### Overall Status: 🟢 {overall_status.upper()}\nAll statutory and grid connection criteria are satisfied.")
    elif overall_status == "Feasible with warnings":
        st.warning(f"### Overall Status: 🟡 {overall_status.upper()}\nProject passes all blocking rules, but one or more operational warnings were flagged.")
    else:
        st.error(f"### Overall Status: 🔴 {overall_status.upper()}\nProject fails one or more mandatory blocking statutory rules.")

    # Top metrics
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total Rules Screened", verdict["total_rules_evaluated"])
    with c2:
        st.metric("Rules Passed", verdict["rules_passed"])
    with c3:
        st.metric("Blocking Failures", len(verdict["blocking_failures"]))
    with c4:
        st.metric("Warnings Flagged", len(verdict["warning_failures"]))

    st.markdown("---")

    # --- Blocking Failures & Actionable Remediation Hints ---
    if verdict["blocking_failures"]:
        st.subheader("🚫 Mandatory Blocking Failures")
        for bf in verdict["blocking_failures"]:
            st.error(
                f"**{bf['rule_id']} - {bf['description']}**\n\n"
                f"- **Measured:** {bf['measured_value']} {bf['unit']} (Threshold: {bf['operator']} {bf['threshold']} {bf['unit']})\n"
                f"- **Explanation:** {bf['explanation']}\n"
                f"- **Source:** {bf['source']}"
            )

    if verdict["remediation_hints"]:
        st.subheader("💡 Actionable Remediation Hints (What Would Make This Feasible)")
        for hint in verdict["remediation_hints"]:
            st.info(f"👉 {hint}")

    st.markdown("---")

    # --- Full Rule Evaluation Table ---
    st.subheader("📊 Detailed Regulatory Screening Table")

    table_records = []
    for ev in evaluations:
        table_records.append({
            "Status": "✅ PASS" if ev.passed else ("🔴 FAIL" if ev.severity == "blocking" else "🟡 WARN"),
            "Rule ID": ev.rule_id,
            "Description": ev.description,
            "Measured": f"{ev.measured_value:.2f}" if isinstance(ev.measured_value, (int, float)) else str(ev.measured_value),
            "Operator": ev.operator,
            "Threshold": f"{ev.threshold:.2f}" if isinstance(ev.threshold, (int, float)) else str(ev.threshold),
            "Unit": ev.unit,
            "Severity": ev.severity.upper(),
            "Regulatory Source": ev.source,
        })

    st.dataframe(pd.DataFrame(table_records), use_container_width=True)

    render_disclaimer_footer()

except MissingInputError as e:
    st.error(f"Missing required configuration key: {e.key}")
    render_disclaimer_footer()
