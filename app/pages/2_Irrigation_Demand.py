"""Page 2: Irrigation Water and Electrical Demand Modeling.

Displays FAO-56 crop coefficient curves, daily and monthly water volume requirements,
pump electrical energy profiles, and feeder supply window constraints.
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
    get_cached_crop_params,
    run_cached_demand,
    render_disclaimer_footer,
    render_scenario_banner,
)
from core.demand.crop_water import calculate_fao56_daily_kc

st.set_page_config(page_title="Irrigation Demand - Feeder Solar DSS", page_icon="💧", layout="wide")

try:
    inputs = get_scenario_inputs()
    render_scenario_banner(inputs.is_illustrative)

    st.title("💧 Page 2: Agricultural Irrigation Energy Demand")
    st.markdown(
        """
        Calculates crop water requirements based on **FAO-56 dual crop coefficients**, effective rainfall,
        and pump electrical energy consumption across the feeder's dedicated 8-hour supply window.
        """
    )

    inputs = get_scenario_inputs()
    schedule_df = get_cached_feeder_schedule()
    weather_df = get_cached_weather()
    crop_params_df = get_cached_crop_params()

    # Get feeder details
    feeder_rows = schedule_df[schedule_df["feeder_name"] == inputs.feeder_name]
    if feeder_rows.empty:
        feeder_row = schedule_df.iloc[0]
    else:
        feeder_row = feeder_rows.iloc[0]

    # Run demand calculation
    crop_mix_tuple = tuple(sorted(inputs.crop_mix_ha.items()))
    irr_methods_tuple = tuple(sorted(inputs.irrigation_methods.items()))

    daily_water_df, hourly_demand_df = run_cached_demand(
        crop_mix_tuple=crop_mix_tuple,
        irrigation_methods_tuple=irr_methods_tuple,
        connected_pump_kw=inputs.connected_pump_kw,
        window_start=feeder_row["window_start"],
        window_end=feeder_row["window_end"],
    )

    # Top KPI metrics
    total_demand_mwh = hourly_demand_df["pump_demand_kwh"].sum() / 1000.0
    total_served_mwh = hourly_demand_df["pump_served_kwh"].sum() / 1000.0
    total_unmet_mwh = hourly_demand_df["pump_unmet_kwh"].sum() / 1000.0
    total_water_m3 = daily_water_df["total_water_volume_m3"].sum()
    peak_demand_kw = hourly_demand_df["pump_demand_kwh"].max()

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.metric(
            "Annual Irrigation Energy Demand",
            f"{total_demand_mwh:.1f} MWh",
            help="Total electrical energy needed to pump irrigation water over the year.",
        )
    with kpi2:
        st.metric(
            "Peak Hourly Pump Demand",
            f"{peak_demand_kw:.1f} kW",
            help="Maximum hourly electrical draw inside the 8h supply window.",
        )
    with kpi3:
        st.metric(
            "Total Irrigation Water Volume",
            f"{total_water_m3 / 1000.0:.1f} thousand m³",
            help=f"{total_water_m3 / 10000.0:.2f} ha-m of gross water pumped.",
        )
    with kpi4:
        if total_unmet_mwh > 0:
            st.metric(
                "Unmet Demand (Window/Pump Limited)",
                f"{total_unmet_mwh:.2f} MWh",
                delta=f"{(total_unmet_mwh / total_demand_mwh) * 100:.1f}% unmet",
                delta_color="inverse",
                help="Portion of daily water requirement that could not be pumped within the 8-hour window at current pump kW.",
            )
        else:
            st.metric(
                "Supply Window Adequacy",
                "100% Served",
                delta="0 unmet MWh",
                delta_color="normal",
                help="The 8-hour window and connected pump capacity are sufficient to deliver all daily water requirements.",
            )

    st.markdown("---")

    # --- Tabbed Deep Dive ---
    tab1, tab2, tab3 = st.tabs(["🌾 Crop Kc Curves", "📅 Monthly & Seasonal Demand", "⏱️ Hourly Profile & Window Constraint"])

    with tab1:
        st.subheader("FAO-56 Crop Coefficient (Kc) Curves Across 2024")
        st.caption("Daily Kc values interpolated across Initial, Development, Mid-Season, and Late stages per FAO-56.")

        # Compute daily Kc series for each crop
        kc_df = pd.DataFrame(index=weather_df.index.normalize().unique())
        for _, cp in crop_params_df.iterrows():
            crop_name = cp["crop"]
            if inputs.crop_mix_ha.get(crop_name, 0.0) > 0:
                kc_df[crop_name] = calculate_fao56_daily_kc(
                    dates=kc_df.index,
                    planting_date_str=str(cp["planting_date"]),
                    l_ini=int(cp["l_ini"]),
                    l_dev=int(cp["l_dev"]),
                    l_mid=int(cp["l_mid"]),
                    l_end=int(cp["l_end"]),
                    kc_ini=float(cp["kc_ini"]),
                    kc_mid=float(cp["kc_mid"]),
                    kc_end=float(cp["kc_end"]),
                )

        fig_kc = px.line(
            kc_df,
            labels={"index": "Date", "value": "Crop Coefficient (Kc)", "variable": "Crop"},
            title="Crop Coefficient Dynamics (FAO-56)",
        )
        fig_kc.update_layout(hovermode="x unified", legend_title_text="Crop", yaxis_range=[0.0, 1.4])
        st.plotly_chart(fig_kc, use_container_width=True)

    with tab2:
        st.subheader("Monthly Irrigation Energy and Water Requirements")

        daily_copy = daily_water_df.copy()
        daily_copy["month"] = daily_copy.index.strftime("%b")
        daily_copy["month_num"] = daily_copy.index.month

        monthly_summary = daily_copy.groupby(["month_num", "month"]).agg({
            "e_el_kwh": lambda x: x.sum() / 1000.0,
            "total_water_volume_m3": lambda x: x.sum() / 1000.0,
            "effective_rain_mm": "sum",
            "et0_mm": "sum",
        }).reset_index().sort_values("month_num")

        monthly_summary.rename(
            columns={
                "e_el_kwh": "Energy Demand (MWh)",
                "total_water_volume_m3": "Water Volume (1000 m³)",
                "effective_rain_mm": "Effective Rain (mm)",
                "et0_mm": "ET₀ (mm)",
            },
            inplace=True,
        )

        fig_month = go.Figure()
        fig_month.add_trace(
            go.Bar(
                x=monthly_summary["month"],
                y=monthly_summary["Energy Demand (MWh)"],
                name="Electricity Demand (MWh)",
                marker_color="#1f77b4",
                yaxis="y",
            )
        )
        fig_month.add_trace(
            go.Scatter(
                x=monthly_summary["month"],
                y=monthly_summary["Effective Rain (mm)"],
                name="Effective Rain (mm)",
                line=dict(color="#2ca02c", width=3),
                yaxis="y2",
            )
        )
        fig_month.update_layout(
            title="Monthly Electricity Demand vs. Effective Rainfall",
            yaxis=dict(title="Energy Demand (MWh)", side="left"),
            yaxis2=dict(title="Effective Rain (mm)", side="right", overlaying="y", showgrid=False),
            legend=dict(x=0.01, y=0.99),
            hovermode="x unified",
        )
        st.plotly_chart(fig_month, use_container_width=True)

        # Seasonal grouping
        st.markdown("##### Seasonal Irrigation Breakdown")
        def get_season(m: int) -> str:
            if m in (6, 7, 8, 9, 10):
                return "Kharif (Monsoon: Jun-Oct)"
            elif m in (11, 12, 1, 2):
                return "Rabi (Winter: Nov-Feb)"
            else:
                return "Summer (Mar-May)"

        daily_copy["season"] = daily_copy["month_num"].apply(get_season)
        seasonal_summary = daily_copy.groupby("season").agg({
            "e_el_kwh": lambda x: round(x.sum() / 1000.0, 1),
            "total_water_volume_m3": lambda x: round(x.sum() / 1000.0, 1),
        }).rename(columns={"e_el_kwh": "Energy Demand (MWh)", "total_water_volume_m3": "Water Volume (1000 m³)"})

        st.table(seasonal_summary)

    with tab3:
        st.subheader("Hourly Profile & Feeder Supply Window Alignment")
        st.markdown(
            f"""
            Feeder **{feeder_row['feeder_name']}** has an active supply window of **{feeder_row['window_start']} to {feeder_row['window_end']}** (8.0 hours).
            All agricultural pumping load is strictly confined within this daytime window.
            """
        )

        selected_month_num = st.selectbox(
            "Select Month to Inspect Average Daily Pumping Profile",
            options=list(range(1, 13)),
            format_func=lambda m: pd.to_datetime(f"2024-{m:02d}-01").strftime("%B"),
            index=2, # March
        )

        month_hourly = hourly_demand_df[hourly_demand_df.index.month == selected_month_num]
        month_hourly["hour_of_day"] = month_hourly.index.hour
        avg_hourly = month_hourly.groupby("hour_of_day")["pump_demand_kwh"].mean().reset_index()

        fig_window = px.bar(
            avg_hourly,
            x="hour_of_day",
            y="pump_demand_kwh",
            labels={"hour_of_day": "Hour of Day (IST)", "pump_demand_kwh": "Average Pump Power (kW)"},
            title=f"Average Daily Pumping Draw Inside Feeder Supply Window - {pd.to_datetime(f'2024-{selected_month_num:02d}-01').strftime('%B')}",
        )
        fig_window.update_layout(xaxis=dict(tickmode="linear", tick0=0, dtick=1))
        st.plotly_chart(fig_window, use_container_width=True)

    render_disclaimer_footer()

except MissingInputError as e:
    st.error(f"Missing required configuration key: {e.key}")
    render_disclaimer_footer()
