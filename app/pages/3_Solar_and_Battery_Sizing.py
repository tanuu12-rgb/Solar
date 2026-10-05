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
    get_cached_feeder_schedule,
    get_cached_weather,
    run_cached_demand,
    run_cached_solar,
    run_cached_dispatch,
    render_disclaimer_footer,
)
from core.solar.pv_model import validate_plant_yield_and_cuf, analyze_feeder_window_coverage
from core.solar.optimizer import run_capacity_optimization_sweep
from core.solar.sensitivity import run_tornado_sensitivity
from core.emissions import calculate_avoided_emissions

st.set_page_config(page_title="Solar & Battery Sizing - Feeder Solar DSS", page_icon="⚡", layout="wide")

try:
    st.title("⚡ Page 3: Solar PV & Battery Storage (BESS) Sizing")
    st.markdown(
        """
        Evaluates solar PV generation via `pvlib`, window capture efficiency across feeders,
        hourly battery dispatch physics, curtailment mitigation, capacity optimization, and parameter sensitivity.
        """
    )

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
    st.subheader("3. CUF Benchmark & Commissioned Plant (2.5 MW) Evaluation")

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
        st.markdown("##### 🏭 Existing Commissioned Plant (2.5 MW) Status")
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

        sweep_df, best_config = run_capacity_optimization_sweep(
            solar_series_per_kwp=solar_df["solar_generation_kwh"] / (inputs.candidate_solar_mwp * 1000.0),
            demand_series_kwh=hourly_demand_df["pump_served_kwh"],
            target_solar_share=inputs.target_solar_share,
        )

        if best_config:
            st.success(
                f"**Recommended Least-Cost Feasible Configuration:**\n"
                f"- **Solar Capacity:** {best_config['solar_mwp']:.1f} MWp\n"
                f"- **Battery Storage:** {best_config['battery_mwh']:.1f} MWh\n"
                f"- **Achieved Solar Share:** {best_config['solar_share_percent']:.1f}%\n"
                f"- **Annualized Cost:** ₹{best_config['total_annualised_cost_inr'] / 1e5:.2f} Lakhs/year "
                f"(₹{best_config['cost_per_kwh_solar_served_inr']:.2f}/kWh solar served)"
            )
        else:
            st.error("No configuration in the sweep range met the target solar share. Consider lowering the target or expanding the sweep.")

        fig_pareto = px.scatter(
            sweep_df,
            x="solar_share_percent",
            y="cost_per_kwh_solar_served_inr",
            size="battery_mwh",
            color="is_feasible",
            hover_data=["solar_mwp", "battery_mwh", "total_annualised_cost_inr"],
            labels={
                "solar_share_percent": "Solar Share (%)",
                "cost_per_kwh_solar_served_inr": "Cost per kWh Solar Served (₹/kWh)",
                "is_feasible": "Meets Target Share",
                "battery_mwh": "Battery (MWh)",
            },
            title="Cost per kWh Solar Served vs. Solar Share (Bubble Size = Battery MWh)",
        )
        st.plotly_chart(fig_pareto, use_container_width=True)

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

    render_disclaimer_footer()

except MissingInputError as e:
    st.error(f"Missing required configuration key: {e.key}")
    render_disclaimer_footer()
