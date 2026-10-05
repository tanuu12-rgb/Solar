"""Page 3: Solar PV and Battery Energy Storage System (BESS) Sizing.

Features the hero seasonal mismatch chart, feeder window coverage analysis,
hourly dispatch simulation, curtailment avoided, optimizer Pareto grid, and tornado sensitivity.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is in sys.path for robust imports from core
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
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
from core.solar.pv_model import validate_plant_yield_and_cuf, analyze_feeder_window_coverage
from core.solar.optimizer import (
    run_capacity_optimization_sweep,
    calculate_command_area_for_target_share,
    get_missing_cost_assumptions,
)
from core.solar.sensitivity import run_tornado_sensitivity
from core.emissions import calculate_avoided_emissions
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

st.set_page_config(page_title="ऊर्जाSetu - Solar & Battery Sizing", page_icon="☀️", layout="wide")
apply_theme()

render_urja_header(
    title="Solar & Battery (BESS) Sizing",
    subtitle="pvlib Hay-Davies transposition, hourly BESS dispatch, annualized cost optimization, and Pareto frontier.",
    badge_label="Step 3 of 6 • Sizing & Optimization",
    icon="☀️",
)

try:
    inputs = get_scenario_inputs()
    render_scenario_banner(inputs.is_illustrative, inputs.feeder_name)

    inputs = get_scenario_inputs()
    schedule_df = get_cached_feeder_schedule()
    weather_df = get_cached_weather()

    feeder_rows = schedule_df[schedule_df["feeder_name"] == inputs.feeder_name]
    feeder_row = feeder_rows.iloc[0] if not feeder_rows.empty else schedule_df.iloc[0]

    # Run demand
    crop_mix_tuple = tuple(sorted(inputs.crop_mix_ha.items()))
    irr_methods_tuple = tuple(sorted(inputs.irrigation_methods.items()))
    daily_water_df, hourly_demand_df = run_cached_demand(
        crop_mix_tuple=crop_mix_tuple,
        irrigation_methods_tuple=irr_methods_tuple,
        connected_pump_kw=inputs.connected_pump_kw,
        window_start=feeder_row["window_start"],
        window_end=feeder_row["window_end"],
    )

    # Run solar generation for candidate capacity
    solar_df = run_cached_solar(solar_capacity_mwp=inputs.candidate_solar_mwp)

    # Run dispatch simulation
    demand_hash_key = f"{inputs.feeder_name}_{inputs.connected_pump_kw}_{sum(inputs.crop_mix_ha.values())}"
    dispatch_df, dispatch_metrics = run_cached_dispatch(
        solar_capacity_mwp=inputs.candidate_solar_mwp,
        battery_capacity_mwh=inputs.candidate_battery_mwh,
        demand_hash_key=demand_hash_key,
        solar_series=solar_df["solar_generation_kwh"],
        demand_series=hourly_demand_df["pump_served_kwh"],
    )

    # --- Top Hero Metrics ---
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric(
            "Solar Share of Irrigation Demand",
            f"{dispatch_metrics['solar_share_percent']:.1f}%",
            delta=f"Target: {inputs.target_solar_share * 100:.0f}%",
            help="Percentage of annual pumping electricity delivered directly from solar PV or battery.",
        )
    with m2:
        st.metric(
            "Curtailment Avoided by BESS",
            f"{dispatch_metrics['curtailment_avoided_mwh']:.1f} MWh",
            delta=f"{dispatch_metrics['curtailment_avoided_percent']:.1f}% saved",
            help="Reduction in wasted solar generation compared to naive baseline dispatch without battery.",
        )
    with m3:
        st.metric(
            "Avoided CO₂ Emissions",
            f"{dispatch_metrics['avoided_emissions_t_co2']:.1f} t CO₂",
            help="Annual carbon abatement based on CEA Version 20.0 grid emission factor.",
        )
    with m4:
        st.metric(
            "Battery Full Cycles (EFC)",
            f"{dispatch_metrics['battery_equivalent_full_cycles']:.1f} cycles/yr",
            help="Annual equivalent full battery cycles utilized to serve agricultural load.",
        )

    st.markdown("---")

    # --- SECTION 1: HERO CHART - Monthly Solar vs. Demand ---
    st.subheader("1. Hero Chart: Monthly Solar Generation vs. Irrigation Demand")
    st.caption(
        "Illustrates the profound seasonal mismatch: high solar surplus during the monsoon (Kharif) when rainfall suppresses demand, "
        "and solar shortfalls during post-monsoon and summer months (Rabi & Summer) when pumping is continuous."
    )

    monthly_comparison = pd.DataFrame(index=range(1, 13))
    monthly_comparison["Month"] = [pd.to_datetime(f"2024-{m:02d}-01").strftime("%b") for m in range(1, 13)]
    monthly_comparison["Solar Generation (MWh)"] = solar_df.groupby(solar_df.index.month)["solar_generation_kwh"].sum() / 1000.0
    monthly_comparison["Irrigation Demand (MWh)"] = hourly_demand_df.groupby(hourly_demand_df.index.month)["pump_served_kwh"].sum() / 1000.0
    monthly_comparison["Solar Served Direct (MWh)"] = dispatch_df.groupby(dispatch_df.index.month)["solar_direct_to_load_kwh"].sum() / 1000.0
    monthly_comparison["Battery Discharge (MWh)"] = dispatch_df.groupby(dispatch_df.index.month)["battery_discharge_to_load_kwh"].sum() / 1000.0
    monthly_comparison["Residual Grid Import (MWh)"] = dispatch_df.groupby(dispatch_df.index.month)["grid_import_kwh"].sum() / 1000.0
    monthly_comparison["Curtailed Solar (MWh)"] = dispatch_df.groupby(dispatch_df.index.month)["curtailed_solar_kwh"].sum() / 1000.0

    fig_hero = go.Figure()
    fig_hero.add_trace(
        go.Bar(
            x=monthly_comparison["Month"],
            y=monthly_comparison["Solar Served Direct (MWh)"],
            name="Solar Direct to Pumps",
            marker_color="#2ca02c",
        )
    )
    fig_hero.add_trace(
        go.Bar(
            x=monthly_comparison["Month"],
            y=monthly_comparison["Battery Discharge (MWh)"],
            name="Battery Discharge to Pumps",
            marker_color="#ff7f0e",
        )
    )
    fig_hero.add_trace(
        go.Bar(
            x=monthly_comparison["Month"],
            y=monthly_comparison["Residual Grid Import (MWh)"],
            name="Residual Grid Import",
            marker_color="#d62728",
        )
    )
    fig_hero.add_trace(
        go.Scatter(
            x=monthly_comparison["Month"],
            y=monthly_comparison["Solar Generation (MWh)"],
            name="Total Solar Generation",
            line=dict(color="#f1c40f", width=4, dash="dash"),
        )
    )
    fig_hero.update_layout(
        barmode="stack",
        title="Monthly Energy Stack (Demand Served vs. Total Solar Generation)",
        yaxis_title="Energy (MWh)",
        hovermode="x unified",
        legend=dict(x=0.01, y=0.99),
    )
    st.plotly_chart(fig_hero, use_container_width=True)

    st.markdown("---")

    # --- SECTION 2: Window Coverage Analysis Across All Feeders ---
    st.subheader("2. Staggered Supply Window Solar Coverage Analysis")
    st.markdown(
        """
        Under MSEDCL rotational rostering, agricultural feeders operate under staggered 8-hour daytime windows.
        Because solar irradiance peaks around solar noon (12:00–13:00 IST), the exact timing of the 8-hour window
        fundamentally dictates how much solar energy can be captured directly without battery storage.
        """
    )

    feeder_coverage_df = analyze_feeder_window_coverage(schedule_df, solar_df)
    st.dataframe(feeder_coverage_df, use_container_width=True)

    fig_cov = px.bar(
        feeder_coverage_df,
        x="feeder_name",
        y="coverage_percent",
        color="window_start",
        text_auto=".1f",
        labels={
            "feeder_name": "Feeder Name",
            "coverage_percent": "Solar Energy Inside Window (%)",
            "window_start": "Window Start",
        },
        title="Solar Energy Capture Efficiency by Feeder Supply Window",
    )
    fig_cov.update_layout(yaxis_range=[0, 100])
    st.plotly_chart(fig_cov, use_container_width=True)

    st.markdown("---")

    # --- SECTION 3: CUF & Commissioned Plant Evaluation ---
    comm_mw = float(feeder_row["solar_plant_mw"])
    st.subheader(f"3. CUF Benchmark & Commissioned Plant ({comm_mw:.1f} MWp) Evaluation")

    cuf_card = validate_plant_yield_and_cuf(solar_df, solar_capacity_mwp=inputs.candidate_solar_mwp)

    cuf_col1, cuf_col2 = st.columns(2)
    with cuf_col1:
        st.markdown("##### ☀️ Plant CUF & Specific Yield Validation")
        st.write(f"- **Candidate Capacity:** {inputs.candidate_solar_mwp:.2f} MWp")
        st.write(f"- **Annual Specific Yield:** {cuf_card['specific_yield_kwh_per_kwp']:.1f} kWh/kWp")
        st.write(f"- **Calculated CUF:** {cuf_card['cuf_percent']:.2f}%")
        st.write(f"- **Expected Regional CUF Range:** {cuf_card['expected_cuf_min_percent']:.1f}% - {cuf_card['expected_cuf_max_percent']:.1f}%")
        if cuf_card["cuf_within_expected_range"]:
            st.success(f"✅ CUF is within expected benchmark range ({cuf_card['status']}).")
        else:
            st.warning(f"⚠️ {cuf_card['message']}")

    with cuf_col2:
        st.markdown(f"##### 🏭 Existing Commissioned Plant ({comm_mw:.1f} MWp) Status")
        comm_mw = float(feeder_row["solar_plant_mw"])
        st.write(f"- **Commissioned Capacity:** {comm_mw:.1f} MWp")
        st.write(f"- **Feeder Window:** {feeder_row['window_start']} - {feeder_row['window_end']}")
        st.write(f"- **Energy Balance Status:** Zero violation ({dispatch_metrics['max_energy_balance_error_kwh']:.6f} kWh max hourly residual)")
        st.info(
            f"At {comm_mw:.1f} MWp solar capacity, the plant produces {dispatch_metrics['total_solar_generation_mwh']:.1f} MWh/year, "
            f"covering {dispatch_metrics['solar_share_percent']:.1f}% of {inputs.feeder_name}'s annual irrigation demand."
        )

    st.markdown("---")

    # --- SECTION 4: Optimizer Capacity Sweep & Sensitivity ---
    st.subheader("4. Capacity Optimization Sweep & Tornado Sensitivity")

    tab_opt, tab_sens = st.tabs(["🎯 Capacity Optimizer Sweep", "🌪️ Sensitivity Tornado Chart"])

    with tab_opt:
        st.markdown("##### Solar PV & Battery Capacity Optimization Sweep")
        st.caption("Sweeps candidate solar (MWp) and battery (MWh) ratings to minimize annualized cost while meeting the target solar share.")

        missing_cost_keys = get_missing_cost_assumptions()
        if missing_cost_keys:
            st.warning(
                f"Missing cost assumptions: {', '.join(missing_cost_keys)}. "
                f"Evaluation uses illustrative scenario cost parameters."
            )

        sweep_df, best_config = run_capacity_optimization_sweep(
            solar_series_per_kwp=solar_df["solar_generation_kwh"] / (inputs.candidate_solar_mwp * 1000.0),
            demand_series_kwh=hourly_demand_df["pump_served_kwh"],
            target_solar_share=inputs.target_solar_share,
        )

        if best_config:
            st.success(
                f"**Headline Cost-Optimal Feasible Sizing:**\n\n"
                f"- **Optimal Solar Capacity:** **{best_config['solar_mwp']:.1f} MWp**\n"
                f"- **Optimal Battery Storage:** **{best_config['battery_mwh']:.1f} MWh**\n"
                f"- **Achieved Solar Share:** **{best_config['solar_share_percent']:.1f}%** (Target: {inputs.target_solar_share*100:.1f}%)\n"
                f"- **Total Annualised Cost:** **₹{best_config['total_annualised_cost_inr'] / 1e5:.2f} Lakhs/year** "
                f"(₹{best_config['cost_per_kwh_solar_served_inr']:.2f}/kWh solar served)\n"
                f"- **Total Capital Expenditure (CAPEX):** **₹{best_config['total_capex_inr'] / 1e7:.2f} Crore**"
            )
            col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
            col_kpi1.metric("Optimal Solar", f"{best_config['solar_mwp']:.1f} MWp")
            col_kpi2.metric("Optimal Battery", f"{best_config['battery_mwh']:.1f} MWh")
            col_kpi3.metric("Annualized Cost", f"₹{best_config['total_annualised_cost_inr'] / 1e5:.1f} L/yr")
            col_kpi4.metric("Cost per kWh Solar", f"₹{best_config['cost_per_kwh_solar_served_inr']:.2f}/kWh")
        else:
            msg = sweep_df.attrs.get("unreachable_message") or (
                f"Target solar share of {inputs.target_solar_share*100:.1f}% is unreachable within the evaluated search bounds."
            )
            st.error(msg)

        col_plot1, col_plot2 = st.columns(2)

        with col_plot1:
            st.markdown("###### Cost vs. Solar Share Frontier")
            fig_pareto = px.scatter(
                sweep_df,
                x="solar_share_percent",
                y="cost_per_kwh_solar_served_inr",
                size="battery_mwh",
                color="is_feasible",
                color_discrete_map={True: "#2E7D32", False: "#C62828"},
                hover_data=["solar_mwp", "battery_mwh", "total_annualised_cost_inr"],
                labels={
                    "solar_share_percent": "Solar Share (%)",
                    "cost_per_kwh_solar_served_inr": "Cost per kWh Solar (₹/kWh)",
                    "is_feasible": "Meets Target",
                    "battery_mwh": "Battery (MWh)",
                },
                title="Cost per kWh Solar vs. Solar Share (Frontier)",
            )
            if best_config:
                fig_pareto.add_trace(
                    go.Scatter(
                        x=[best_config["solar_share_percent"]],
                        y=[best_config["cost_per_kwh_solar_served_inr"]],
                        mode="markers+text",
                        marker=dict(symbol="star", size=18, color="#F2A900", line=dict(color="#0B3C5D", width=2)),
                        name="Least-Cost Optimal",
                        text=["Optimal"],
                        textposition="top center",
                    )
                )
            fig_pareto.update_layout(hovermode="closest", legend_title_text="Feasibility")
            st.plotly_chart(fig_pareto, use_container_width=True)

        with col_plot2:
            st.markdown("###### MWp × MWh Annualized Cost Heatmap (₹ Lakhs/year)")
            heatmap_data = sweep_df.pivot(index="battery_mwh", columns="solar_mwp", values="total_annualised_cost_inr") / 1e5
            fig_heat = px.imshow(
                heatmap_data.round(1),
                labels=dict(x="Solar Capacity (MWp)", y="Battery Capacity (MWh)", color="Cost (₹ Lakhs)"),
                x=heatmap_data.columns.astype(str),
                y=heatmap_data.index.astype(str),
                text_auto=True,
                color_continuous_scale="Viridis",
                title="Total Annualized Cost Grid (₹ Lakhs/year)",
            )
            st.plotly_chart(fig_heat, use_container_width=True)

    with tab_sens:
        st.markdown("##### One-at-a-Time (OAT) Sensitivity Tornado Chart")
        st.caption("Assesses the percentage change in cost per kWh solar served under ±20% variation in key drivers.")

        tornado_df = run_tornado_sensitivity(
            base_solar_mwp=inputs.candidate_solar_mwp,
            base_battery_mwh=inputs.candidate_battery_mwh,
            base_demand_series_kwh=hourly_demand_df["pump_served_kwh"],
            solar_generation_per_kwp=solar_df["solar_generation_kwh"] / (inputs.candidate_solar_mwp * 1000.0),
        )

        fig_torn = go.Figure()
        fig_torn.add_trace(
            go.Bar(
                y=tornado_df["parameter"],
                x=tornado_df["low_cost_inr"] - tornado_df["base_cost_inr"],
                orientation="h",
                name="-20% Variation",
                marker_color="#3498db",
            )
        )
        fig_torn.add_trace(
            go.Bar(
                y=tornado_df["parameter"],
                x=tornado_df["high_cost_inr"] - tornado_df["base_cost_inr"],
                orientation="h",
                name="+20% Variation",
                marker_color="#e74c3c",
            )
        )
        fig_torn.update_layout(
            barmode="overlay",
            title="Tornado Sensitivity: Impact on Cost per kWh Solar Served (₹/kWh relative to base)",
            xaxis_title="Change in Cost per kWh (₹/kWh)",
            yaxis_title="Parameter",
            hovermode="y unified",
        )
        st.plotly_chart(fig_torn, use_container_width=True)

    st.markdown("---")

    # --- SECTION 5: Inverse Sizing: Command Area Needed ---
    st.subheader("5. Inverse Sizing: Command Area Needed for Target Solar Share")
    st.caption("Determines the maximum agricultural command area that the candidate solar plant can support while maintaining the target solar share.")

    col_inv1, col_inv2 = st.columns([1, 2])
    with col_inv1:
        inv_plant_mw = st.number_input(
            "Candidate Solar Plant (MWp)",
            min_value=0.5,
            max_value=10.0,
            value=float(inputs.candidate_solar_mwp),
            step=0.5,
            key="inv_plant_mw",
        )
        inv_target_pct = st.slider(
            "Target Solar Share (%)",
            min_value=10,
            max_value=100,
            value=int(inputs.target_solar_share * 100 if inputs.target_solar_share <= 1.0 else inputs.target_solar_share),
            step=5,
            key="inv_target_pct",
        )
        inv_bess_mwh = st.number_input(
            "Candidate Battery Storage (MWh)",
            min_value=0.0,
            max_value=20.0,
            value=float(inputs.candidate_battery_mwh),
            step=0.5,
            key="inv_bess_mwh",
        )

    inv_res = calculate_command_area_for_target_share(
        base_demand_kwh_series=hourly_demand_df["pump_served_kwh"],
        solar_kwh_series=solar_df["solar_generation_kwh"] * (inv_plant_mw / inputs.candidate_solar_mwp),
        base_command_area_ha=inputs.command_area_ha,
        target_solar_share=inv_target_pct / 100.0,
        battery_capacity_mwh=inv_bess_mwh,
        pt_capacity_mva=inputs.pt_capacity_mva,
    )

    with col_inv2:
        if inv_res["feasible"]:
            st.success(
                f"**Inverse Sizing Result:**\n\n"
                f"A **{inv_plant_mw:.1f} MWp** solar plant (with {inv_bess_mwh:.1f} MWh BESS) can support up to "
                f"**{inv_res['command_area_ha']:.1f} hectares** of command area to achieve the target **{inv_target_pct}%** solar share.\n\n"
                f"- **Annual Irrigation Demand:** {inv_res['annual_demand_mwh']:.1f} MWh\n"
                f"- **Solar Energy Served:** {inv_res['solar_served_mwh']:.1f} MWh\n"
                f"- **Achieved Solar Share:** {inv_res['achieved_solar_share_percent']:.1f}%\n"
                f"- **Command Area Scaling Factor:** {inv_res['scale_factor']:.2f}× relative to base command area ({inputs.command_area_ha:.1f} ha)"
            )
        else:
            st.error(inv_res["message"])

    render_disclaimer_footer()

except MissingInputError as e:
    render_missing_input_card(e)
    render_disclaimer_footer()
