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
    """Pydantic model representing user-defined scenario inputs for a feeder."""

    substation: str = Field(default="33/11 kV Bhatangali")
    feeder_name: str = Field(default="11KV BHATANGALI")
    crop_mix_ha: Dict[str, float] = Field(
        default_factory=lambda: {
            "Soybean": 120.0,
            "Gram": 80.0,
            "Sugarcane": 25.0,
            "Tur": 30.0,
            "Wheat": 20.0,
        }
    )
    irrigation_methods: Dict[str, str] = Field(
        default_factory=lambda: {
            "Soybean": "sprinkler",
            "Gram": "drip",
            "Sugarcane": "drip",
            "Tur": "flood",
            "Wheat": "sprinkler",
        }
    )
    connected_pump_kw: float = Field(default=1200.0, ge=10.0, le=20000.0)
    candidate_solar_mwp: float = Field(default=2.5, ge=0.1, le=50.0)
    candidate_battery_mwh: float = Field(default=2.0, ge=0.0, le=50.0)
    target_solar_share: float = Field(default=0.70, ge=0.1, le=1.0)
    available_land_acres: float = Field(default=15.0, ge=0.5, le=500.0)
    distance_to_substation_km: float = Field(default=1.8, ge=0.1, le=50.0)


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
    """Return provenance summary for all local raw data files."""
    root = Path(__file__).resolve().parent.parent
    files = [
        ("Weather Data (Open-Meteo 2024 IST)", root / "data" / "raw" / "open-meteo-18.38N76.54E633m.csv"),
        ("Feeder Supply Schedules (MSEDCL Annexure-A)", root / "data" / "raw" / "feeder_schedule.csv"),
        ("Crop Growth Parameters (FAO-56 Tables 11/12)", root / "data" / "raw" / "crop_params.csv"),
    ]
    records = []
    for label, path in files:
        if path.exists():
            records.append({
                "dataset": label,
                "filename": path.name,
                "size_kb": round(path.stat().st_size / 1024.0, 1),
                "sha256": compute_file_sha256(path),
            })
        else:
            records.append({
                "dataset": label,
                "filename": path.name,
                "size_kb": 0.0,
                "sha256": "MISSING",
            })
    return records


def get_scenario_inputs() -> ScenarioInputs:
    """Retrieve or initialize ScenarioInputs from Streamlit session state."""
    if "scenario_inputs" not in st.session_state:
        st.session_state.scenario_inputs = ScenarioInputs()
    return st.session_state.scenario_inputs


def save_scenario_inputs(inputs: ScenarioInputs) -> None:
    """Save ScenarioInputs to Streamlit session state."""
    st.session_state.scenario_inputs = inputs


@st.cache_data
def run_cached_demand(
    crop_mix_tuple: Tuple[Tuple[str, float], ...],
    irrigation_methods_tuple: Tuple[Tuple[str, str], ...],
    connected_pump_kw: float,
    window_start: str,
    window_end: str,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Calculate daily water requirement and 8,784h pump electrical demand profile."""
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
def run_cached_solar(solar_capacity_mwp: float) -> pd.DataFrame:
    """Simulate 8,784h solar generation profile with pvlib."""
    weather_df = get_cached_weather()
    return simulate_pv_generation(
        weather_df=weather_df,
        solar_capacity_mwp=solar_capacity_mwp,
    )


@st.cache_data
def run_cached_dispatch(
    solar_capacity_mwp: float,
    battery_capacity_mwh: float,
    demand_hash_key: str,
    solar_series: pd.Series,
    demand_series: pd.Series,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Simulate hourly dispatch and calculate key metrics."""
    return simulate_hourly_dispatch(
        solar_generation_kwh=solar_series,
        pump_demand_kwh=demand_series,
        battery_capacity_mwh=battery_capacity_mwh,
    )


def render_disclaimer_footer() -> None:
    """Render mandatory UI disclaimer (PROJECT_SPEC Section 0 Rule 9)."""
    st.markdown("---")
    st.caption(
        "**Disclaimer:** This is an early-stage decision-support tool, not a replacement for detailed "
        "DISCOM engineering studies. Weather data reflects a single historical year (2024) and crop areas "
        "are user-specified feeder-level inputs."
    )
