"""Unit tests for FAO-56 crop water requirements and pump electrical demand."""

import numpy as np
import pandas as pd
import pytest

from core.demand.crop_water import (
    calculate_fao56_daily_kc,
    calculate_effective_rainfall_usda,
    calculate_daily_crop_water_requirements,
)
from core.demand.pump_energy import calculate_pump_energy_from_volume
from core.demand.hourly_profile import build_hourly_irrigation_demand_profile
from core.data.loaders import load_weather_data, load_crop_parameters


def test_fao56_kc_interpolation_stages() -> None:
    """Verify linear interpolation of Kc across initial, dev, mid, and late stages."""
    dates = pd.date_range("2024-06-25", periods=135, freq="D")
    kc_series = calculate_fao56_daily_kc(
        dates=dates,
        planting_date_str="06-25",
        l_ini=20,
        l_dev=30,
        l_mid=60,
        l_end=25,
        kc_ini=0.40,
        kc_mid=1.15,
        kc_end=0.50,
    )

    # Initial stage (days 0 to 19): Kc should equal kc_ini
    assert np.isclose(kc_series.iloc[0], 0.40, atol=1e-3)
    assert np.isclose(kc_series.iloc[19], 0.40, atol=1e-3)

    # Mid stage (day 20+30 = day 50 through day 109): Kc should equal kc_mid
    assert np.isclose(kc_series.iloc[50], 1.15, atol=1e-3)
    assert np.isclose(kc_series.iloc[100], 1.15, atol=1e-3)

    # Late stage end (day 134): Kc should be approaching kc_end (within 0.05)
    assert np.isclose(kc_series.iloc[134], 0.50, atol=0.05)


def test_effective_rainfall_usda_limits() -> None:
    """Verify USDA SCS effective rainfall equation edge cases."""
    # When rain = 0, effective rain = 0
    assert calculate_effective_rainfall_usda(0.0) == 0.0

    # Low rainfall (< 250 mm)
    p_low = 100.0
    # Formula: P * (125 - 0.2 * 100) / 125 = 100 * 105 / 125 = 84.0 mm
    assert np.isclose(calculate_effective_rainfall_usda(p_low), 84.0, atol=1e-2)

    # High rainfall (> 250 mm)
    p_high = 300.0
    # Formula: 125 + 0.1 * 300 = 155.0 mm
    assert np.isclose(calculate_effective_rainfall_usda(p_high), 155.0, atol=1e-2)


def test_pump_energy_hand_calculation() -> None:
    """Verify pump energy calculation matches analytical physics formula."""
    # Volume: 10,000 m3
    # H = groundwater_depth (18.5) + drawdown (4.5) + friction (3.0) = 26.0 m
    # E_hyd = 1000 * 9.81 * 26.0 * 10000 / 3.6e6 = 708.5 kWh
    # eta_pump = 0.72, eta_motor = 0.85 -> combined = 0.612
    # E_el = 708.5 / 0.612 = 1157.68 kWh
    e_hyd, e_el = calculate_pump_energy_from_volume(10000.0)
    assert np.isclose(e_hyd, 708.5, atol=1.0)
    assert np.isclose(e_el, 1157.68, atol=2.0)




def test_hourly_profile_unmet_demand_trigger() -> None:
    """Verify that when daily demand exceeds window delivery at pump kW, unmet demand is logged."""
    dates = pd.date_range("2024-03-01 00:00:00", "2024-03-01 23:00:00", freq="1h")
    daily_df = pd.DataFrame(
        {"e_el_kwh": [5000.0]},  # 5,000 kWh required in one day
        index=pd.to_datetime(["2024-03-01"]),
    )

    # Supply window: 8 hours (10:00 to 18:00)
    # Connected pump capacity: 200 kW -> Max deliverable in 8 hours = 200 kW * 8h = 1,600 kWh
    hourly_df = build_hourly_irrigation_demand_profile(
        daily_demand_df=daily_df,
        hourly_timestamps=dates,
        window_start="10:00",
        window_end="18:00",
        connected_pump_capacity_kw=200.0,
    )

    # Demand served should equal exactly 1,600 kWh
    assert np.isclose(hourly_df["pump_served_kwh"].sum(), 1600.0, atol=1e-3)
    # Unmet demand should equal 5,000 - 1,600 = 3,400 kWh
    assert np.isclose(hourly_df["pump_unmet_kwh"].sum(), 3400.0, atol=1e-3)
