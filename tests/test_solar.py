"""Unit tests for solar PV generation, CUF validation, and feeder window coverage."""

import numpy as np
import pandas as pd

from core.data.loaders import load_weather_data, load_feeder_schedule
from core.solar.pv_model import (
    simulate_pv_generation,
    validate_plant_yield_and_cuf,
    analyze_feeder_window_coverage,
)


def test_solar_generation_scaling() -> None:
    """Verify simulate_pv_generation produces positive AC power and scales linearly with capacity."""
    weather_df = load_weather_data()

    # 1.0 MWp plant
    gen_1mw = simulate_pv_generation(weather_df, solar_capacity_mwp=1.0)
    assert len(gen_1mw) == 8784
    assert (gen_1mw["solar_generation_kwh"] >= 0.0).all()

    # 2.0 MWp plant
    gen_2mw = simulate_pv_generation(weather_df, solar_capacity_mwp=2.0)
    # Total annual generation should scale proportionally by factor of 2.0
    ratio = gen_2mw["solar_generation_kwh"].sum() / gen_1mw["solar_generation_kwh"].sum()
    assert np.isclose(ratio, 2.0, atol=1e-3)


def test_validate_plant_yield_and_cuf() -> None:
    """Verify CUF and specific yield validation card against SECI reference range."""
    weather_df = load_weather_data()
    gen_df = simulate_pv_generation(weather_df, solar_capacity_mwp=2.5)
    cuf_card = validate_plant_yield_and_cuf(gen_df, solar_capacity_mwp=2.5)

    assert "cuf_percent" in cuf_card
    assert "specific_yield_kwh_per_kwp" in cuf_card
    assert "cuf_within_expected_range" in cuf_card

    # For Latur (GHI ~1900 kWh/m2), specific yield is typically 1500 - 1750 kWh/kWp
    # CUF = Specific Yield / 8784 * 100% -> around 17% - 21%
    assert 15.0 <= cuf_card["cuf_percent"] <= 25.0
    assert 1400.0 <= cuf_card["specific_yield_kwh_per_kwp"] <= 2000.0


def test_feeder_window_coverage_analysis() -> None:
    """Verify window coverage analysis computes coverage percentages for all feeders."""
    weather_df = load_weather_data()
    schedule_df = load_feeder_schedule()
    gen_df = simulate_pv_generation(weather_df, solar_capacity_mwp=2.5)

    coverage_df = analyze_feeder_window_coverage(schedule_df, gen_df)
    assert len(coverage_df) == len(schedule_df)

    for _, row in coverage_df.iterrows():
        # Feeder windows capture a significant fraction of solar generation (typically 65% - 95%)
        assert 50.0 <= row["coverage_percent"] <= 100.0
        assert row["window_solar_generation_mwh"] <= row["total_annual_generation_mwh"]
