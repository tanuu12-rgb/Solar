"""Page 5: GIS-Based Connection Route & Transmission Loss Modeling.

Calculates route length, voltage selection (11 kV vs 33 kV), 3-phase I2R peak/annual
losses, infrastructure line cost, and optional GeoJSON obstacle avoidance.
"""

from __future__ import annotations

import sys
import json
from pathlib import Path

# Ensure project root is in sys.path for robust imports from core
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
import pydeck as pdk
import streamlit as st

from core.errors import MissingInputError
from app.state import (
    get_scenario_inputs,
    save_scenario_inputs,
    get_illustrative_scenario_inputs,
    run_cached_solar,
    render_disclaimer_footer,
    render_scenario_banner,
)
from core.gis.route import calculate_connection_route, RouteResult
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

st.set_page_config(page_title="ऊर्जाSetu - Connection Route", page_icon="🗺️", layout="wide")
apply_theme()

render_urja_header(
    title="GIS Evacuation Route & Loss Analysis",
    subtitle="Interactive geospatial routing, 11 kV vs 33 kV voltage selection, line CAPEX, and 3-phase I²R power loss modeling.",
    badge_label="Step 5 of 6 • Geospatial Route",
    icon="🗺️",
)

try:
    inputs = get_scenario_inputs()
    render_scenario_banner(inputs.is_illustrative, inputs.feeder_name)

    solar_df = run_cached_solar(solar_capacity_mwp=inputs.candidate_solar_mwp)

    st.markdown("---")
    st.subheader("1. Interconnection Coordinates & Obstacle Layer")

    col_coords1, col_coords2 = st.columns(2)

    with col_coords1:
        st.markdown("##### 📍 Candidate Solar Plant Location")
        plant_lat = st.number_input(
            "Plant Latitude (°N)",
            min_value=17.0,
            max_value=20.0,
            value=float(inputs.plant_lat or 18.3750),
            format="%.4f",
            key="gis_plant_lat",
        )
        plant_lon = st.number_input(
            "Plant Longitude (°E)",
            min_value=75.0,
            max_value=78.0,
            value=float(inputs.plant_lon or 76.5350),
            format="%.4f",
            key="gis_plant_lon",
        )

    with col_coords2:
        st.markdown("##### 🏢 33/11 kV Substation Location")
        sub_lat = st.number_input(
            "Substation Latitude (°N)",
            min_value=17.0,
            max_value=20.0,
            value=float(inputs.substation_lat or 18.3800),
            format="%.4f",
            key="gis_sub_lat",
        )
        sub_lon = st.number_input(
            "Substation Longitude (°E)",
            min_value=75.0,
            max_value=78.0,
            value=float(inputs.substation_lon or 76.5400),
            format="%.4f",
            key="gis_sub_lon",
        )

    # Save coordinates back to session state
    inputs.plant_lat = plant_lat
    inputs.plant_lon = plant_lon
    inputs.substation_lat = sub_lat
    inputs.substation_lon = sub_lon
    save_scenario_inputs(inputs)

    # Optional obstacle GeoJSON upload
    st.markdown("##### 🏞️ Environmental & Physical Obstacle Layer (Optional)")
    obstacle_file = st.file_uploader(
        "Upload Obstacle GeoJSON (forests, water bodies, urban settlements to route around)",
        type=["geojson", "json"],
        help="If uploaded, a least-cost grid path avoidance algorithm will route around the obstacle polygons.",
    )

    obstacle_geojson = None
    if obstacle_file is not None:
        try:
            obstacle_geojson = json.load(obstacle_file)
            st.success(f"Loaded obstacle layer: {len(obstacle_geojson.get('features', []))} obstacle feature(s).")
        except Exception as e:
            st.error(f"Malformed GeoJSON file: {e}")

    # Compute Connection Route
    route_result: RouteResult = calculate_connection_route(
        plant_lat=plant_lat,
        plant_lon=plant_lon,
        substation_lat=sub_lat,
        substation_lon=sub_lon,
        plant_mw=inputs.candidate_solar_mwp,
        obstacle_geojson=obstacle_geojson,
        hourly_solar_generation_kwh=solar_df["solar_generation_kwh"],
    )

    st.markdown("---")
    st.subheader("2. Interconnection Route & Electrical Loss KPIs")

    # Routing Method Banner
    st.info(f"**Applied Routing Method:** `{route_result.method}`")

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.metric(
            "Route Length",
            f"{route_result.route_km:.2f} km",
            f"Straight-line: {route_result.straight_line_km:.2f} km",
        )
    with kpi2:
        st.metric(
            "Evacuation Voltage",
            f"{route_result.voltage_kv:.0f} kV",
            "MSEDCL Standard",
        )
    with kpi3:
        st.metric(
            "Peak I²R Line Loss",
            f"{route_result.peak_loss_kw:.1f} kW",
            f"Peak Current: {route_result.peak_current_a:.1f} A",
        )
    with kpi4:
        st.metric(
            "Annual Loss & Cost",
            f"{route_result.annual_loss_mwh:.1f} MWh ({route_result.loss_pct:.2f}%)",
            f"₹{route_result.total_infrastructure_cost_inr / 1e5:.2f} Lakhs Capex",
        )

    st.markdown("---")
    st.subheader("3. Interactive GIS Route Map")

    # Construct PyDeck Visualization
    mid_lat = (plant_lat + sub_lat) / 2.0
    mid_lon = (plant_lon + sub_lon) / 2.0

    view_state = pdk.ViewState(
        latitude=mid_lat,
        longitude=mid_lon,
        zoom=13,
        pitch=0,
    )

    # Nodes layer
    nodes_data = [
        {"name": f"Solar Plant ({inputs.candidate_solar_mwp:.1f} MWp)", "lat": plant_lat, "lon": plant_lon, "color": [46, 125, 50, 220], "radius": 80},
        {"name": f"Substation ({inputs.substation})", "lat": sub_lat, "lon": sub_lon, "color": [11, 60, 93, 220], "radius": 80},
    ]

    nodes_layer = pdk.Layer(
        "ScatterplotLayer",
        data=nodes_data,
        get_position=["lon", "lat"],
        get_color="color",
        get_radius="radius",
        pickable=True,
        auto_highlight=True,
    )

    # Route path layer
    path_data = [
        {"path": route_result.coordinates_path, "name": f"{route_result.voltage_kv:.0f} kV Route ({route_result.route_km:.2f} km)"}
    ]

    path_layer = pdk.Layer(
        "PathLayer",
        data=path_data,
        get_path="path",
        get_color=[242, 169, 0, 240],  # Solar Amber
        width_scale=1,
        width_min_pixels=4,
        pickable=True,
        auto_highlight=True,
    )

    deck_layers = [path_layer, nodes_layer]

    deck = pdk.Deck(
        layers=deck_layers,
        initial_view_state=view_state,
        tooltip={"text": "{name}"},
        map_style="road",
    )

    st.pydeck_chart(deck, use_container_width=True)

    st.markdown("---")
    st.subheader("4. Detailed Electrical Loss & Infrastructure Cost Breakdown")

    col_loss, col_cost = st.columns(2)

    with col_loss:
        st.markdown("##### ⚡ Transmission Electrical Parameters")
        st.table(pd.DataFrame([
            {"Parameter": "Evacuation Voltage Level", "Value": f"{route_result.voltage_kv:.0f} kV"},
            {"Parameter": "Conductor Positive-Sequence Resistance (R)", "Value": f"{route_result.conductor_resistance_ohm_per_km:.2f} Ω/km"},
            {"Parameter": "Conductor Inductive Reactance (X)", "Value": f"{route_result.conductor_reactance_ohm_per_km:.2f} Ω/km"},
            {"Parameter": "Total Line Resistance", "Value": f"{route_result.conductor_resistance_ohm_per_km * route_result.route_km:.3f} Ω"},
            {"Parameter": "Peak Line Current (Full Generation)", "Value": f"{route_result.peak_current_a:.2f} A"},
            {"Parameter": "Peak 3-Phase I²R Line Loss", "Value": f"{route_result.peak_loss_kw:.2f} kW"},
            {"Parameter": "Annual Energy Loss", "Value": f"{route_result.annual_loss_mwh:.2f} MWh/year"},
            {"Parameter": "Loss Percentage of Solar Generation", "Value": f"{route_result.loss_pct:.2f}%"},
        ]))

    with col_cost:
        st.markdown("##### 💰 Interconnection Infrastructure Capital Cost")
        st.table(pd.DataFrame([
            {"Component": f"Overhead Line ({route_result.voltage_kv:.0f} kV)", "Unit Rate": f"₹{route_result.line_capex_per_km_inr/1e5:.2f} L/km", "Cost": f"₹{route_result.line_capex_total_inr/1e5:.2f} Lakhs"},
            {"Component": "Dedicated Substation Feeder Bay", "Unit Rate": f"₹{route_result.substation_bay_cost_inr/1e5:.2f} L/bay", "Cost": f"₹{route_result.substation_bay_cost_inr/1e5:.2f} Lakhs"},
            {"Component": "**Total Connection Infrastructure CAPEX**", "Unit Rate": "-", "Cost": f"**₹{route_result.total_infrastructure_cost_inr/1e5:.2f} Lakhs**"},
        ]))

    st.download_button(
        label="📥 Download Route GeoJSON",
        data=json.dumps(route_result.geojson, indent=2),
        file_name=f"feeder_solar_route_{inputs.feeder_name}.geojson",
        mime="application/geo+json",
    )

    render_disclaimer_footer()

except MissingInputError as e:
    render_missing_input_card(e)
    render_disclaimer_footer()
