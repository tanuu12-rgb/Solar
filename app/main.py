"""Smart Feeder Solarization Planning and Decision Support System (Latur, Maharashtra).

Main landing page introducing the decision-support system, the 33/11 kV Bhatangali case study,
and key engineering capabilities.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is in sys.path for robust imports from core
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st
from core.errors import MissingInputError
from app.state import (
    get_scenario_inputs,
    get_cached_feeder_schedule,
    get_cached_weather,
    get_cached_crop_params,
    render_disclaimer_footer,
)

st.set_page_config(
    page_title="Feeder Solarization DSS - Latur",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded",
)

try:
    st.title("☀️ Smart Feeder Solarization Planning & Decision Support System")
    st.subheader("Agricultural Feeder Solarization under PM-KUSUM Component-C (Latur District, Maharashtra)")

    st.markdown(
        """
        Welcome to the **Decision Support System (DSS)** for solarizing rural agricultural feeders in Maharashtra.
        This tool models the real physics, agronomy, and economics of dedicated 11 kV agricultural feeders to determine
        the optimal solar PV and battery energy storage system (BESS) sizing to provide daytime power to farmers.
        """
    )

    # Case study highlight card
    inputs = get_scenario_inputs()
    schedule_df = get_cached_feeder_schedule()
    weather_df = get_cached_weather()
    crop_params_df = get_cached_crop_params()

    st.markdown("### 📍 Active Case Study: 33/11 kV Bhatangali Substation")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            label="Substation Location",
            value="Latur Taluka",
            help="District: Latur, Maharashtra. Lat: 18.38°N, Lon: 76.54°E",
        )
    with col2:
        st.metric(
            label="Power Transformer Capacity",
            value="5.0 MVA",
            help="Substation transformer capacity from MSEDCL feeder schedule",
        )
    with col3:
        st.metric(
            label="Commissioned Solar Plant",
            value="2.5 MWp",
            help="Existing solar plant capacity from MSEDCL Annexure-A letter",
        )
    with col4:
        st.metric(
            label="Connected Dedicated Ag Feeders",
            value=f"{len(schedule_df)} Feeders",
            help="3 feeders with staggered 8-hour daytime supply windows",
        )

    st.markdown("---")

    st.markdown("### 🔍 Key Engineering Capabilities & Analysis Workflow")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            """
            #### 1. Real Agronomic Water Demand
            - **FAO-56 Dual Kc Formulation**: Crop water requirements across Kharif, Rabi, and Summer seasons.
            - **Local Crop Mix**: Soybean, Gram, Sugarcane, Tur, and Wheat.
            - **Pump Energy Physics**: Total Dynamic Head (TDH), static groundwater depth (CGWB), and pump efficiency.
            - **Window Constraint**: Demands distributed strictly across the 8-hour feeder supply window.
            """
        )
    with c2:
        st.markdown(
            """
            #### 2. Rigorous Solar & Battery Modeling
            - **pvlib POA Transposition**: Hay-Davies model with Faiman cell temperature modeling.
            - **Staggered Supply Window Analysis**: Quantify solar energy captured by different feeder timing windows.
            - **BESS Simulation**: C-rate limits, symmetric efficiency, state-of-charge constraints, and cycle counting.
            - **Hourly Energy Balance**: Zero-tolerance conservation verification on every hourly step.
            """
        )
    with c3:
        st.markdown(
            """
            #### 3. Economics & Regulatory Feasibility
            - **Capacity Optimizer**: Sweep solar and battery capacities to minimize annualized cost per kWh solar served.
            - **Curtailment Avoided**: Benchmark battery dispatch against naive baseline dispatch.
            - **Regulatory Rule Screening**: Deterministic screening against MSEDCL circulars and PM-KUSUM guidelines.
            - **Avoided Emissions**: CO₂ reductions benchmarked against CEA grid baseline.
            """
        )

    st.markdown("---")

    st.markdown("### 📋 Navigation Guide")
    st.info(
        """
        Use the sidebar to explore each stage of the analysis:
        - **Page 1: Inputs & Data**: Configure feeder selection, crop mix, pump capacity, review data quality audit, and analyze supply window solar coverage for all feeders.
        - **Page 2: Irrigation Demand**: Inspect crop water requirements, Kc curves, seasonal MWh demand, and window constraints.
        - **Page 3: Solar & Battery Sizing**: View the hero supply vs. demand mismatch chart, window coverage, battery dispatch, and optimizer sweep.
        - **Page 4: Feasibility**: Review the deterministic regulatory screening verdict, blocking rules, and remediation hints.
        - **Page 5: Summary Report**: Export an executive brief with key technical, financial, and environmental metrics.
        - **Page 6: Assumptions & Sources**: Complete transparent audit table of all 67 assumptions and data provenance hashes.
        """
    )

    render_disclaimer_footer()

except MissingInputError as e:
    st.error(f"Missing required configuration key: {e.key}")
    render_disclaimer_footer()
