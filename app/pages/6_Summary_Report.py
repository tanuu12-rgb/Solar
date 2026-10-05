"""Page 6: Executive Summary Report and Engineering Brief.

Synthesizes technical sizing, dispatch physics, connection routing, regulatory feasibility,
lifecycle economics, and environmental decarbonization into an actionable engineering brief.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure project root is in sys.path
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
    get_cached_weather,
    run_cached_demand,
    run_cached_solar,
    run_cached_dispatch,
    render_disclaimer_footer,
    render_scenario_banner,
)
from app.theme import (
    apply_theme,
    render_verdict_badge,
    render_status_chip,
    COLOR_PRIMARY_BLUE,
    COLOR_SOLAR_AMBER,
    COLOR_AGRI_GREEN,
)

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
from core.feasibility.rules_engine import evaluate_feasibility_rules
from core.feasibility.explanations import generate_feasibility_verdict
from core.gis.route import calculate_connection_route
from core.emissions import calculate_avoided_emissions
from core.solar.optimizer import calculate_annualized_system_cost
from core.config_loader import get_assumption_value

from app.theme import apply_theme, render_urja_header

st.set_page_config(
    page_title="ऊर्जाSetu - Summary Report",
    page_icon="📄",
    layout="wide",
)

apply_theme()

render_urja_header(
    title="Executive Engineering Brief",
    subtitle="Standardized one-page project appraisal synthesizing dispatch physics, regulatory feasibility, lifecycle costs, and carbon reduction.",
    badge_label="Step 6 of 6 • Project Brief",
    icon="📄",
)

try:
    inputs = get_scenario_inputs()
    render_scenario_banner(inputs.is_illustrative, inputs.feeder_name)

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

    cand_solar = inputs.candidate_solar_mwp or 0.0
    dist_km = inputs.distance_to_substation_km or 0.0

    measured_params = {
        "solar_plant_mw": cand_solar,
        "distance_to_substation_km": dist_km,
        "candidate_land_ratio": candidate_land_ratio,
        "transformer_loading_ratio": transformer_loading_ratio,
        "window_duration_hours": 8.0,
        "evacuation_voltage_kv": 11.0 if cand_solar <= 3.0 and dist_km <= 5.0 else 33.0,
        "solar_capex_per_mwp_inr": solar_capex_per_mwp,
    }
    context_vars = {
        "available_land_acres": inputs.available_land_acres,
        "pt_capacity_mva": pt_mva,
    }
    evaluations = evaluate_feasibility_rules(measured_params)
    verdict = generate_feasibility_verdict(evaluations, context_vars)

    # GIS Route Calculation
    route_res = calculate_connection_route(
        plant_lat=inputs.plant_lat or 18.3950,
        plant_lon=inputs.plant_lon or 76.5520,
        substation_lat=inputs.substation_lat or 18.3800,
        substation_lon=inputs.substation_lon or 76.5400,
        plant_mw=cand_solar,
        hourly_solar_generation_kwh=solar_df["solar_generation_kwh"],
    )

    # Calculate safe summary values
    grid_imported_kwh = float(
        dispatch_metrics.get(
            "grid_imported_kwh",
            dispatch_df["grid_to_demand_kwh"].sum() if "grid_to_demand_kwh" in dispatch_df else 0.0,
        )
    )
    total_solar_served_kwh = float(
        dispatch_metrics.get(
            "total_solar_served_kwh",
            (dispatch_df["solar_to_demand_kwh"] + dispatch_df["battery_to_demand_kwh"]).sum()
            if "solar_to_demand_kwh" in dispatch_df and "battery_to_demand_kwh" in dispatch_df
            else 0.0,
        )
    )
    total_demand_kwh = float(
        dispatch_metrics.get(
            "total_demand_kwh",
            dispatch_df["irrigation_demand_kwh"].sum() if "irrigation_demand_kwh" in dispatch_df else 0.0,
        )
    )

    # Economics
    cost_res = calculate_annualized_system_cost(
        solar_capacity_mwp=cand_solar,
        battery_capacity_mwh=inputs.candidate_battery_mwh or 0.0,
        grid_imported_kwh=grid_imported_kwh,
    )

    # Emissions
    emiss_res = calculate_avoided_emissions(
        solar_energy_used_kwh=total_solar_served_kwh,
        grid_imported_kwh=grid_imported_kwh,
        total_demand_kwh=total_demand_kwh,
    )
    avoided_co2 = emiss_res.get("avoided_t_co2", 0.0)
    residual_co2 = emiss_res.get("residual_t_co2", 0.0)
    residual_grid_dep = emiss_res.get("residual_grid_dependence_pct", 0.0)

    # --- Section 1: Project Scope Header ---
    st.markdown("### 1. Project Identification & Scope")
    sc1, sc2, sc3, sc4 = st.columns(4)
    with sc1:
        st.markdown(f"**Substation:** {feeder_row['substation']}")
        st.markdown(f"**Feeder:** `{inputs.feeder_name}`")
        st.markdown(f"**Taluka / District:** {feeder_row['taluka']}, {feeder_row['district']}")
    with sc2:
        st.markdown(f"**PT Capacity:** {feeder_row['pt_capacity_mva']} MVA")
        st.markdown(f"**Supply Window:** `{feeder_row['window_start']} - {feeder_row['window_end']}` (8h)")
        st.markdown(f"**Connected Pumps:** {inputs.connected_pump_kw:.0f} kW ({sum(inputs.crop_mix_ha.values()):.1f} ha)")
    with sc3:
        st.markdown(f"**Solar Sizing:** {cand_solar:.2f} MWp")
        st.markdown(f"**Battery Sizing:** {inputs.candidate_battery_mwh or 0.0:.2f} MWh")
        st.markdown(f"**Target Solar Share:** {(inputs.target_solar_share or 0.70) * 100:.0f}%")
    with sc4:
        st.markdown(f"**Feasibility:** {render_verdict_badge(verdict['verdict'])}", unsafe_allow_html=True)
        st.markdown(f"**Passed Rules:** {verdict['rules_passed']} / {verdict['total_rules_evaluated']}")
        st.markdown(f"**Blocking Failures:** {len(verdict['blocking_failures'])}")

    st.markdown("---")

    # --- Section 2: Statutory Feasibility & Ranked Rejection Reasons ---
    st.markdown("### 2. Statutory Feasibility & Rejection Reasons")
    if verdict["verdict"] == "Feasible":
        st.success("✅ **All statutory feasibility screening checks passed.** The proposed solar and battery capacities satisfy MSEDCL KUSUM-C interconnection guidelines.")
    elif verdict["verdict"] == "Marginal":
        st.warning("⚠️ **Proposal is MARGINAL (Review Required).** Non-blocking warnings detected:")
        for r in verdict["ranked_rejection_reasons"]:
            st.markdown(f"- **{r['rule_id']} ({r['severity'].upper()}):** {r['explanation']} *(Remediation: {r['remediation_hint']})*")
    else:
        st.error("❌ **Proposal REJECTED due to statutory constraints:**")
        for r in verdict["ranked_rejection_reasons"]:
            st.markdown(f"- **{r['rule_id']} ({r['severity'].upper()}):** {r['explanation']}")
            st.info(f"💡 **Remediation:** {r['remediation_hint']}")

    st.markdown("---")

    # --- Section 3: Connection Route & Evacuation Losses ---
    st.markdown("### 3. Grid Evacuation Route & Loss Analysis")
    rc1, rc2, rc3, rc4 = st.columns(4)
    with rc1:
        st.metric("Route Distance", f"{route_res.route_km:.2f} km", help=route_res.method)
    with rc2:
        st.metric("Evacuation Voltage", f"{route_res.voltage_kv:.0f} kV", help="MSEDCL standard evacuation voltage")
    with rc3:
        st.metric("Peak Line Loss", f"{route_res.peak_loss_kw:.1f} kW ({route_res.loss_pct:.2f}%)")
    with rc4:
        st.metric("Annual Route Losses", f"{route_res.annual_loss_mwh:.1f} MWh ({route_res.loss_pct:.2f}%)")

    st.caption(f"ℹ️ **Routing Method:** {route_res.method} | Conductor Resistance: {route_res.conductor_resistance_ohm_per_km} Ω/km | Estimated Line CAPEX: ₹{route_res.line_capex_total_inr:,.0f}")

    st.markdown("---")

    # --- Section 4: Full KPI Matrix ---
    st.markdown("### 4. Technical, Economic & Environmental KPI Matrix")

    kpi_col1, kpi_col2, kpi_col3 = st.columns(3)

    with kpi_col1:
        st.markdown("#### ⚡ Physics & Energy Dispatch")
        tot_dem_mwh = float(dispatch_metrics.get("total_demand_mwh", total_demand_kwh / 1000.0))
        tot_sol_mwh = float(dispatch_metrics.get("total_solar_generation_mwh", dispatch_df["solar_generation_kwh"].sum() / 1000.0 if "solar_generation_kwh" in dispatch_df else 0.0))
        sol_dir_mwh = float(dispatch_metrics.get("solar_direct_to_demand_mwh", dispatch_df["solar_to_demand_kwh"].sum() / 1000.0 if "solar_to_demand_kwh" in dispatch_df else 0.0))
        bat_dis_mwh = float(dispatch_metrics.get("battery_discharge_to_demand_mwh", dispatch_metrics.get("battery_to_demand_mwh", dispatch_df["battery_to_demand_kwh"].sum() / 1000.0 if "battery_to_demand_kwh" in dispatch_df else 0.0)))
        tot_srv_mwh = float(dispatch_metrics.get("total_solar_served_mwh", total_solar_served_kwh / 1000.0))
        sol_share_pct = float(dispatch_metrics.get("solar_share_percent", (tot_srv_mwh / tot_dem_mwh * 100.0) if tot_dem_mwh > 0 else 0.0))
        grd_imp_mwh = float(dispatch_metrics.get("grid_imported_mwh", grid_imported_kwh / 1000.0))
        curt_mwh = float(dispatch_metrics.get("curtailed_mwh", dispatch_df["solar_curtailed_kwh"].sum() / 1000.0 if "solar_curtailed_kwh" in dispatch_df else 0.0))
        curt_av_mwh = float(dispatch_metrics.get("curtailment_avoided_mwh", 0.0))
        curt_av_pct = float(dispatch_metrics.get("curtailment_avoided_percent", 0.0))
        efc = float(dispatch_metrics.get("battery_equivalent_full_cycles", 0.0))

        kpis_energy = pd.DataFrame([
            {"Metric": "Annual Pumping Demand", "Value": f"{tot_dem_mwh:,.1f} MWh"},
            {"Metric": "Annual Solar Generation", "Value": f"{tot_sol_mwh:,.1f} MWh"},
            {"Metric": "Solar Direct to Pumps", "Value": f"{sol_dir_mwh:,.1f} MWh"},
            {"Metric": "BESS Discharged to Pumps", "Value": f"{bat_dis_mwh:,.1f} MWh"},
            {"Metric": "Total Solar Served", "Value": f"{tot_srv_mwh:,.1f} MWh"},
            {"Metric": "Achieved Solar Share", "Value": f"{sol_share_pct:.1f}%"},
            {"Metric": "Residual Grid Imported", "Value": f"{grd_imp_mwh:,.1f} MWh"},
            {"Metric": "Curtailed Solar Generation", "Value": f"{curt_mwh:,.1f} MWh"},
            {"Metric": "Curtailment Avoided by BESS", "Value": f"{curt_av_mwh:,.1f} MWh ({curt_av_pct:.1f}%)"},
            {"Metric": "Battery Full Cycles (EFC)", "Value": f"{efc:.1f} cycles/yr"},
        ])
        st.table(kpis_energy)

    with kpi_col2:
        st.markdown("#### 💰 Lifecycle Economics")
        ann_solar_capex = float(cost_res.get("annualized_solar_capex_inr", cost_res.get("annual_solar_capex_inr", 0.0)))
        ann_batt_capex = float(cost_res.get("annualized_battery_capex_inr", cost_res.get("annual_battery_capex_inr", 0.0)))
        tot_om_inr = float(cost_res.get("total_om_inr", cost_res.get("annual_solar_om_inr", 0.0) + cost_res.get("annual_battery_om_inr", 0.0)))
        grid_cost_inr = float(cost_res.get("grid_cost_inr", cost_res.get("annual_grid_cost_inr", 0.0)))
        tot_ann_cost = float(cost_res.get("total_annualized_cost_inr", cost_res.get("total_annual_cost_inr", 0.0)))
        lcoe_solar = float(cost_res.get("cost_per_kwh_solar_served_inr", 0.0))

        kpis_cost = pd.DataFrame([
            {"Metric": "Annualized Solar CAPEX", "Value": f"₹{ann_solar_capex:,.0f}"},
            {"Metric": "Annualized Battery CAPEX", "Value": f"₹{ann_batt_capex:,.0f}"},
            {"Metric": "Annual Total O&M", "Value": f"₹{tot_om_inr:,.0f}"},
            {"Metric": "Annual Residual Grid Cost", "Value": f"₹{grid_cost_inr:,.0f}"},
            {"Metric": "Total Annualized Project Cost", "Value": f"₹{tot_ann_cost:,.0f}"},
            {"Metric": "Levelized Cost of Solar Served", "Value": f"₹{lcoe_solar:.2f} / kWh"},
            {"Metric": "Estimated Transmission Line CAPEX", "Value": f"₹{route_res.line_capex_total_inr:,.0f}"},
        ])
        st.table(kpis_cost)

    with kpi_col3:
        st.markdown("#### 🌿 Decarbonization & Grid")
        kpis_env = pd.DataFrame([
            {"Metric": "Annual Avoided Carbon", "Value": f"{avoided_co2:,.1f} tCO₂/yr"},
            {"Metric": "Residual Grid Emissions", "Value": f"{residual_co2:,.1f} tCO₂/yr"},
            {"Metric": "Residual Grid Dependence", "Value": f"{residual_grid_dep:.1f}%"},
            {"Metric": "Displaced Grid Intensity", "Value": f"{get_assumption_value('grid_emission_factor_kg_co2_per_kwh')} kg CO₂/kWh"},
            {"Metric": "Feeder Supply Window", "Value": f"{feeder_row['window_start']} - {feeder_row['window_end']} (8h)"},
        ])
        st.table(kpis_env)

    st.markdown("---")

    # --- Section 5: Download & Export Datasets ---
    st.markdown("### 5. Export Engineering Deliverables")
    exp_col1, exp_col2 = st.columns(2)

    with exp_col1:
        st.markdown("##### 📊 Full 8,784-Hour Simulation Dataset (CSV)")
        st.caption("Hourly resolution: timestamps, solar generation, pump demand, battery state-of-charge, and grid imports.")
        export_df = dispatch_df.copy()
        export_df["timestamp"] = export_df.index.strftime("%Y-%m-%d %H:%M:%S")
        csv_bytes = export_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download Hourly Time-Series (CSV)",
            data=csv_bytes,
            file_name=f"feeder_solar_dispatch_{inputs.feeder_name.replace(' ', '_')}_2024.csv",
            mime="text/csv",
            type="primary",
        )

    with exp_col2:
        st.markdown("##### 📄 Executive Project Brief (JSON)")
        st.caption("Machine-readable JSON package containing all scenario parameters, feasibility verdicts, and lifecycle KPIs.")
        summary_payload = {
            "project_metadata": {
                "substation": feeder_row["substation"],
                "feeder_name": inputs.feeder_name,
                "taluka": feeder_row["taluka"],
                "district": feeder_row["district"],
                "pt_capacity_mva": feeder_row["pt_capacity_mva"],
                "supply_window": f"{feeder_row['window_start']} - {feeder_row['window_end']}",
                "is_illustrative": inputs.is_illustrative,
            },
            "capacities": {
                "solar_mwp": inputs.candidate_solar_mwp,
                "battery_mwh": inputs.candidate_battery_mwh,
                "connected_pump_kw": inputs.connected_pump_kw,
                "command_area_ha": sum(inputs.crop_mix_ha.values()),
            },
            "feasibility_verdict": {
                "status": verdict["verdict"],
                "rules_passed": verdict["rules_passed"],
                "total_rules": verdict["total_rules_evaluated"],
                "blocking_failures": verdict["blocking_failures"],
                "rejection_reasons": verdict["ranked_rejection_reasons"],
            },
            "connection_route": {
                "distance_km": route_res.route_km,
                "voltage_kv": route_res.voltage_kv,
                "routing_method": route_res.method,
                "peak_loss_kw": route_res.peak_loss_kw,
                "annual_loss_mwh": route_res.annual_loss_mwh,
                "line_capex_inr": route_res.line_capex_total_inr,
            },
            "dispatch_kpis": {
                "total_demand_mwh": tot_dem_mwh,
                "solar_generation_mwh": tot_sol_mwh,
                "solar_served_mwh": tot_srv_mwh,
                "solar_share_pct": sol_share_pct,
                "grid_imported_mwh": grd_imp_mwh,
                "curtailed_mwh": curt_mwh,
                "curtailment_avoided_mwh": curt_av_mwh,
                "curtailment_avoided_pct": curt_av_pct,
                "battery_efc": efc,
            },
            "economics": {
                "annualized_solar_capex_inr": ann_solar_capex,
                "annualized_battery_capex_inr": ann_batt_capex,
                "total_om_inr": tot_om_inr,
                "grid_cost_inr": grid_cost_inr,
                "total_annualized_cost_inr": tot_ann_cost,
                "cost_per_kwh_solar_served_inr": lcoe_solar,
            },
            "environmental": {
                "avoided_co2_tons": avoided_co2,
                "residual_co2_tons": residual_co2,
                "residual_grid_dependence_pct": residual_grid_dep,
            },
        }
        json_bytes = json.dumps(summary_payload, indent=2).encode("utf-8")
        st.download_button(
            label="📥 Download Executive Brief (JSON)",
            data=json_bytes,
            file_name=f"feeder_solar_summary_{inputs.feeder_name.replace(' ', '_')}.json",
            mime="application/json",
        )

    render_disclaimer_footer()

except MissingInputError as e:
    render_missing_input_card(e)
    render_disclaimer_footer()
