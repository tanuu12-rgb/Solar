"""Page 5: Executive Summary Report and Data Export.

Generates a concise one-page engineering and financial summary for the feeder solarization project,
with downloadable CSV and JSON exports.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is in sys.path for robust imports from core
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import json
import pandas as pd
import streamlit as st

from core.errors import MissingInputError
from app.state import (
    get_scenario_inputs,
    get_cached_feeder_schedule,
    get_cached_weather,
    run_cached_demand,
    run_cached_solar,
    run_cached_dispatch,
    render_disclaimer_footer,
)
from core.feasibility.rules_engine import evaluate_feasibility_rules
from core.feasibility.explanations import generate_feasibility_verdict
from core.config_loader import get_assumption_value

st.set_page_config(page_title="Executive Summary - Feeder Solar DSS", page_icon="📄", layout="wide")

try:
    st.title("📄 Page 5: Executive Summary & Project Brief")
    st.markdown(
        """
        Synthesizes the technical sizing, dispatch physics, regulatory feasibility, and environmental metrics
        into a standardized one-page engineering brief suitable for DISCOM and nodal agency review.
        """
    )

    inputs = get_scenario_inputs()
    schedule_df = get_cached_feeder_schedule()
    weather_df = get_cached_weather()

    feeder_rows = schedule_df[schedule_df["feeder_name"] == inputs.feeder_name]
    feeder_row = feeder_rows.iloc[0] if not feeder_rows.empty else schedule_df.iloc[0]

    # Run demand, solar, dispatch
    crop_mix_tuple = tuple(sorted(inputs.crop_mix_ha.items()))
    irr_methods_tuple = tuple(sorted(inputs.irrigation_methods.items()))
    daily_water_df, hourly_demand_df = run_cached_demand(
        crop_mix_tuple=crop_mix_tuple,
        irrigation_methods_tuple=irr_methods_tuple,
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

    # Feasibility evaluation
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
    context_vars = {"available_land_acres": inputs.available_land_acres, "pt_capacity_mva": pt_mva}
    evaluations = evaluate_feasibility_rules(measured_params)
    verdict = generate_feasibility_verdict(evaluations, context_vars)

    # --- Project Header Card ---
    st.subheader("1. Project Identification & Scope")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.write(f"**Substation:** {feeder_row['substation']}")
        st.write(f"**Feeder Name:** {inputs.feeder_name}")
        st.write(f"**Taluka / District:** {feeder_row['taluka']}, {feeder_row['district']}")
    with col2:
        st.write(f"**Power Transformer:** {feeder_row['pt_capacity_mva']} MVA")
        st.write(f"**Feeder Window:** {feeder_row['window_start']} - {feeder_row['window_end']}")
        st.write(f"**Window Duration:** 8.0 Hours")
    with col3:
        st.write(f"**Proposed Solar:** {inputs.candidate_solar_mwp:.1f} MWp")
        st.write(f"**Proposed BESS:** {inputs.candidate_battery_mwh:.1f} MWh")
        st.write(f"**Target Solar Share:** {inputs.target_solar_share * 100:.0f}%")
    with col4:
        status_color = "🟢" if verdict["overall_status"] == "Feasible" else ("🟡" if "warning" in verdict["overall_status"] else "🔴")
        st.write(f"**Feasibility Verdict:** {status_color} {verdict['overall_status']}")
        st.write(f"**Rules Passed:** {verdict['rules_passed']} / {verdict['total_rules_evaluated']}")
        st.write(f"**Blocking Failures:** {len(verdict['blocking_failures'])}")

    st.markdown("---")

    # --- Executive KPI Summary Table ---
    st.subheader("2. Key Performance Indicators (KPIs)")

    summary_kpis = {
        "Metric": [
            "Annual Irrigation Pumping Demand",
            "Total Solar PV Generation",
            "Solar Energy Delivered Directly to Pumps",
            "Battery Energy Discharged to Pumps",
            "Total Demand Served by Solar + Storage",
            "Achieved Solar Share of Demand",
            "Residual Pumping Energy Imported from Grid",
            "Total Curtailed Solar Generation",
            "Solar Curtailment Avoided by Battery",
            "Solar Curtailment Avoided (%)",
            "Annual Battery Equivalent Full Cycles (EFC)",
            "Annual Avoided Carbon Emissions",
        ],
        "Value": [
            f"{dispatch_metrics['total_demand_mwh']:,.1f}",
            f"{dispatch_metrics['total_solar_generation_mwh']:,.1f}",
            f"{dispatch_metrics['solar_direct_to_demand_mwh']:,.1f}",
            f"{dispatch_metrics['battery_discharge_to_demand_mwh']:,.1f}",
            f"{dispatch_metrics['total_solar_served_mwh']:,.1f}",
            f"{dispatch_metrics['solar_share_percent']:.1f}%",
            f"{dispatch_metrics['grid_imported_mwh']:,.1f}",
            f"{dispatch_metrics['curtailed_mwh']:,.1f}",
            f"{dispatch_metrics['curtailment_avoided_mwh']:,.1f}",
            f"{dispatch_metrics['curtailment_avoided_percent']:.1f}%",
            f"{dispatch_metrics['battery_equivalent_full_cycles']:.1f}",
            f"{dispatch_metrics['avoided_emissions_t_co2']:,.1f}",
        ],
        "Unit": [
            "MWh/year",
            "MWh/year",
            "MWh/year",
            "MWh/year",
            "MWh/year",
            "%",
            "MWh/year",
            "MWh/year",
            "MWh/year",
            "%",
            "cycles/year",
            "tons CO₂/year",
        ],
    }
    st.table(pd.DataFrame(summary_kpis))

    st.markdown("---")

    # --- Data Export Section ---
    st.subheader("💾 Export Analysis Datasets")
    col_exp1, col_exp2 = st.columns(2)

    # Prepare CSV export of hourly dispatch
    with col_exp1:
        st.markdown("##### Full 8,784-Hour Simulation Dataset")
        st.caption("Hourly resolution: timestamps, solar generation, pump demand, battery dispatch, and grid import.")
        export_df = dispatch_df.copy()
        export_df["timestamp"] = export_df.index.strftime("%Y-%m-%d %H:%M:%S")
        csv_bytes = export_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download Hourly Simulation (CSV)",
            data=csv_bytes,
            file_name=f"feeder_solar_dispatch_{inputs.feeder_name.replace(' ', '_')}_2024.csv",
            mime="text/csv",
            type="primary",
        )

    # Prepare JSON export of executive summary
    with col_exp2:
        st.markdown("##### Executive Summary & Metadata")
        st.caption("Machine-readable JSON containing project inputs, KPIs, and regulatory feasibility verdicts.")
        summary_dict = {
            "metadata": {
                "substation": feeder_row["substation"],
                "feeder_name": inputs.feeder_name,
                "taluka": feeder_row["taluka"],
                "district": feeder_row["district"],
                "weather_year": 2024,
                "window": f"{feeder_row['window_start']}-{feeder_row['window_end']}",
            },
            "inputs": inputs.model_dump(),
            "kpis": dispatch_metrics,
            "feasibility": verdict,
        }
        json_bytes = json.dumps(summary_dict, indent=2).encode("utf-8")
        st.download_button(
            label="📥 Download Executive Summary (JSON)",
            data=json_bytes,
            file_name=f"feeder_solar_summary_{inputs.feeder_name.replace(' ', '_')}.json",
            mime="application/json",
        )

    render_disclaimer_footer()

except MissingInputError as e:
    st.error(f"Missing required configuration key: {e.key}")
    render_disclaimer_footer()
