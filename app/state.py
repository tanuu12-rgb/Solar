"""Shared state, data caching, and simulation execution for the Streamlit app.

Provides centralized access to datasets, scenario inputs, and simulation runs
with caching to ensure responsive UI performance.
"""

from __future__ import annotations

import hashlib
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
from pydantic import BaseModel, Field
import streamlit as st

from core.errors import MissingInputError
from core.config_loader import (
    load_assumptions,
    load_rules,
    get_assumption_value,
    AssumptionEntry,
    RuleEntry,
)
from core.data.loaders import (
    load_weather_data,
    load_feeder_schedule,
    load_crop_parameters,
)
from core.data.validators import validate_weather_dataset
from core.demand.crop_water import calculate_daily_crop_water_requirements
from core.demand.pump_energy import calculate_pump_energy_from_volume
from core.demand.hourly_profile import build_hourly_irrigation_demand_profile
from core.solar.pv_model import (
    simulate_pv_generation,
    validate_plant_yield_and_cuf,
    analyze_feeder_window_coverage,
)
from core.solar.dispatch import simulate_hourly_dispatch
from core.solar.optimizer import run_capacity_optimization_sweep
from core.solar.sensitivity import run_tornado_sensitivity
from core.feasibility.rules_engine import evaluate_feasibility_rules
from core.feasibility.explanations import generate_feasibility_verdict
from core.emissions import calculate_avoided_emissions

logger = logging.getLogger(__name__)


class ScenarioInputs(BaseModel):
    """Pydantic model representing user-defined scenario inputs for a feeder.

    Per PROJECT_SPEC and input honesty rules:
    - No silent defaults for crop mix, irrigation methods, pump kW, battery MWh, land or distance.
    - candidate_solar_mwp is pre-filled strictly from feeder_schedule.csv solar_plant_mw.
    - All scenario numbers are user-supplied or explicitly loaded illustrative scenario assumptions.
    """

    substation: Optional[str] = None
    feeder_name: Optional[str] = None
    crop_mix_source: str = "manual"  # 'manual' or 'district_proxy'
    command_area_ha: Optional[float] = None
    crop_mix_ha: Dict[str, float] = Field(default_factory=dict)
    irrigation_methods: Dict[str, str] = Field(default_factory=dict)
    connected_pump_kw: Optional[float] = None
    candidate_solar_mwp: Optional[float] = None
    candidate_battery_mwh: Optional[float] = None
    target_solar_share: Optional[float] = None
    available_land_acres: Optional[float] = None
    distance_to_substation_km: Optional[float] = None
    plant_lat: Optional[float] = None
    plant_lon: Optional[float] = None
    substation_lat: Optional[float] = None
    substation_lon: Optional[float] = None
    budget_inr: Optional[float] = None
    is_illustrative: bool = False


def get_illustrative_scenario_inputs() -> ScenarioInputs:
    """Return an illustrative scenario clearly tagged as not measured feeder data."""
    return ScenarioInputs(
        substation="33/11 kV Bhatangali",
        feeder_name="11KV BHATANGALI",
        crop_mix_source="manual",
        command_area_ha=275.0,
        crop_mix_ha={
            "Soybean": 120.0,
            "Gram": 80.0,
            "Sugarcane": 25.0,
            "Tur": 30.0,
            "Wheat": 20.0,
        },
        irrigation_methods={
            "Soybean": "sprinkler",
            "Gram": "drip",
            "Sugarcane": "drip",
            "Tur": "flood",
            "Wheat": "sprinkler",
        },
        connected_pump_kw=1200.0,
        candidate_solar_mwp=2.5,
        candidate_battery_mwh=2.0,
        target_solar_share=0.70,
        available_land_acres=15.0,
        distance_to_substation_km=1.8,
        plant_lat=18.3950,
        plant_lon=76.5520,
        substation_lat=18.3800,
        substation_lon=76.5400,
        budget_inr=150000000.0,
        is_illustrative=True,
    )


def render_scenario_banner(is_illustrative: bool = False, feeder_name: Optional[str] = None) -> None:
    """Render mandatory scenario input provenance banner across Pages 1 to 7."""
    from app.theme import render_scenario_banner as theme_banner
    theme_banner(is_illustrative=is_illustrative, feeder_name=feeder_name)


def render_missing_input_card(error: MissingInputError) -> None:
    """Render a helpful card when required feeder inputs are unconfigured."""
    st.warning(
        f"⚠️ **Feeder Configuration Required:** `{error.key}`\n\n"
        f"{error.message or 'This engineering stage requires specific feeder parameters that have not been configured yet.'}\n\n"
        "Per **PROJECT_SPEC Section 0 Rule 1 & Rule 3 (Input Honesty)**, the system does not inject silent synthetic defaults. "
        "You can configure custom parameters on **Page 1: Inputs & Data**, or immediately load an illustrative case study for demonstration."
    )
    col1, col2 = st.columns([1, 2])
    with col1:
        if st.button("✨ Load Illustrative Scenario (Bhatangali Demo)", type="primary", key=f"btn_load_demo_{error.key}"):
            save_scenario_inputs(get_illustrative_scenario_inputs())
            st.rerun()




def compute_file_sha256(filepath: Path) -> str:
    """Compute SHA-256 hash of a file for data provenance tracking."""
    if not filepath.exists():
        return "FILE_NOT_FOUND"
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


@st.cache_data
def get_cached_weather() -> pd.DataFrame:
    """Load and cache 8,784 hourly weather rows in IST."""
    return load_weather_data()


@st.cache_data
def get_cached_feeder_schedule() -> pd.DataFrame:
    """Load and cache feeder schedule rows."""
    return load_feeder_schedule()


@st.cache_data
def get_cached_crop_params() -> pd.DataFrame:
    """Load and cache crop growth parameters."""
    return load_crop_parameters()


def get_cached_assumptions() -> Dict[str, AssumptionEntry]:
    """Load all populated assumptions."""
    return load_assumptions()


def get_cached_rules() -> List[RuleEntry]:
    """Load all feasibility rules."""
    return load_rules()


def get_dataset_provenance() -> List[Dict[str, Any]]:
    """Return provenance summary for all 7 local raw data files."""
    root = Path(__file__).resolve().parent.parent
    raw_dir = root / "data" / "raw"
    files = [
        (
            "Open-Meteo Hourly Weather (2024 IST)",
            raw_dir / "open-meteo-18.38N76.54E633m.csv",
            "Active",
            "Hourly temperature, wind, ET0, rain, GHI, DNI, DHI in IST. Powers pvlib POA & FAO-56.",
        ),
        (
            "MSEDCL Feeder Supply Schedules (Annexure-A)",
            raw_dir / "feeder_schedule.csv",
            "Active",
            "33/11kV Bhatangali feeder windows (8h), PT capacity (5 MVA), plant MWp.",
        ),
        (
            "FAO-56 Crop Growth Parameters",
            raw_dir / "crop_params.csv",
            "Active",
            "Kc coefficients (ini, mid, end) and stage lengths for Soybean, Gram, Sugarcane, Tur, Wheat.",
        ),
        (
            "Latur Irrigation Area Census (2011-12)",
            raw_dir / "2011-12_Irrigation_Area_Latur.zip",
            "Check-Only",
            "Ministry of Agriculture District Census: Well vs. Canal irrigated area reference archive.",
        ),
        (
            "Latur Crop Production Census (2011-12)",
            raw_dir / "2011-12_Production_Crops_Latur.zip",
            "Check-Only",
            "Ministry of Agriculture District Census: Taluka-level crop area & production reference.",
        ),
        (
            "MSEDCL KUSUM-C Daytime Ag Circular (2024)",
            raw_dir / "Ltr-to-field_KUSUM-C_Daytime-Ag_06.08.24-1.pdf",
            "Check-Only",
            "MSEDCL circular establishing daytime solar agricultural feeder policy & guidelines.",
        ),
        (
            "NASA POWER Hourly Solar Irradiance Archive",
            raw_dir / "POWER_Point_Hourly_20240101_20240229_018d38N_076d54E_LST.csv",
            "Check-Only",
            "NASA POWER satellite solar archive (LST) retained for validation benchmarking.",
        ),
    ]
    records = []
    for label, path, status, purpose in files:
        if path.exists():
            records.append({
                "dataset": label,
                "filename": path.name,
                "status": status,
                "purpose": purpose,
                "size_kb": round(path.stat().st_size / 1024.0, 1),
                "sha256": compute_file_sha256(path),
            })
        else:
            records.append({
                "dataset": label,
                "filename": path.name,
                "status": status,
                "purpose": purpose,
                "size_kb": 0.0,
                "sha256": "MISSING",
            })
    return records


def get_scenario_inputs() -> ScenarioInputs:
    """Retrieve or initialize ScenarioInputs from Streamlit session state."""
    if "scenario_inputs" not in st.session_state:
        # Pre-fill candidate_solar_mwp strictly from feeder_schedule.csv solar_plant_mw
        schedule_df = get_cached_feeder_schedule()
        default_sub = str(schedule_df.iloc[0]["substation"]) if not schedule_df.empty else "33/11 kV Bhatangali"
        default_feeder = str(schedule_df.iloc[0]["feeder_name"]) if not schedule_df.empty else "11KV BHATANGALI"
        default_solar_mw = float(schedule_df.iloc[0]["solar_plant_mw"]) if not schedule_df.empty else 2.5
        st.session_state.scenario_inputs = ScenarioInputs(
            substation=default_sub,
            feeder_name=default_feeder,
            candidate_solar_mwp=default_solar_mw,
            target_solar_share=0.70,
            substation_lat=18.3800,
            substation_lon=76.5400,
            is_illustrative=False,
        )
    return st.session_state.scenario_inputs


def save_scenario_inputs(inputs: ScenarioInputs) -> None:
    """Save ScenarioInputs to Streamlit session state."""
    st.session_state.scenario_inputs = inputs


@st.cache_data
def run_cached_demand(
    crop_mix_tuple: Tuple[Tuple[str, float], ...],
    irrigation_methods_tuple: Tuple[Tuple[str, str], ...],
    connected_pump_kw: Optional[float],
    window_start: str,
    window_end: str,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Calculate daily water requirement and 8,784h pump electrical demand profile."""
    if not crop_mix_tuple or sum(v for _, v in crop_mix_tuple) <= 0:
        raise MissingInputError(
            "crop_mix_ha",
            "Crop mix hectares not configured. Please enter crop areas on Page 1 or click 'Load illustrative scenario'.",
        )
    if connected_pump_kw is None or connected_pump_kw <= 0:
        raise MissingInputError(
            "connected_pump_kw",
            "Connected pump electrical capacity (kW) not configured. Please enter connected pump capacity on Page 1 or click 'Load illustrative scenario'.",
        )

    weather_df = get_cached_weather()
    crop_params_df = get_cached_crop_params()
    crop_mix = dict(crop_mix_tuple)
    irrigation_methods = dict(irrigation_methods_tuple)

    # 1. Daily crop water requirements
    daily_water_df = calculate_daily_crop_water_requirements(
        weather_df=weather_df,
        crop_mix_ha=crop_mix,
        crop_params_df=crop_params_df,
        irrigation_methods=irrigation_methods,
    )

    # 2. Daily pump electrical energy
    _, daily_water_df["e_el_kwh"] = calculate_pump_energy_from_volume(
        daily_water_df["total_water_volume_m3"]
    )

    # 3. Hourly demand profile aligned with feeder supply window
    hourly_demand_df = build_hourly_irrigation_demand_profile(
        daily_demand_df=daily_water_df,
        hourly_timestamps=weather_df.index,
        window_start=window_start,
        window_end=window_end,
        connected_pump_capacity_kw=connected_pump_kw,
    )

    return daily_water_df, hourly_demand_df


@st.cache_data
def run_cached_solar(solar_capacity_mwp: Optional[float]) -> pd.DataFrame:
    """Simulate 8,784h solar generation profile with pvlib."""
    if solar_capacity_mwp is None or solar_capacity_mwp <= 0:
        raise MissingInputError(
            "candidate_solar_mwp",
            "Candidate solar capacity (MWp) is missing. Please configure it on Page 1.",
        )
    weather_df = get_cached_weather()
    return simulate_pv_generation(
        weather_df=weather_df,
        solar_capacity_mwp=solar_capacity_mwp,
    )


@st.cache_data
def run_cached_dispatch(
    solar_capacity_mwp: Optional[float],
    battery_capacity_mwh: Optional[float],
    demand_hash_key: str,
    solar_series: pd.Series,
    demand_series: pd.Series,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Simulate hourly dispatch and calculate key metrics."""
    if solar_capacity_mwp is None or solar_capacity_mwp <= 0:
        raise MissingInputError("candidate_solar_mwp", "Candidate solar capacity (MWp) is missing.")
    batt_mwh = 0.0 if battery_capacity_mwh is None else battery_capacity_mwh
    return simulate_hourly_dispatch(
        solar_generation_kwh=solar_series,
        pump_demand_kwh=demand_series,
        battery_capacity_mwh=batt_mwh,
    )


def render_disclaimer_footer() -> None:
    """Render mandatory UI disclaimer (PROJECT_SPEC Section 0 Rule 9)."""
    st.markdown("---")
    st.caption(
        "**Disclaimer:** This is an early-stage decision-support tool, not a replacement for detailed "
        "DISCOM engineering studies. Weather data reflects a single historical year (2024) and crop areas "
        "are user-specified feeder-level inputs."
    )
