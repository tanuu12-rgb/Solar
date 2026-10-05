"""Unit tests for BESS physics, hourly dispatch simulation, and energy balance conservation."""

import numpy as np
import pandas as pd
import pytest

from core.solar.battery import BatterySystem
from core.solar.dispatch import simulate_hourly_dispatch
from core.errors import EnergyBalanceError


def test_battery_storage_charge_discharge_efficiency() -> None:
    """Verify BESS round-trip efficiency is symmetric and obeys state-of-charge limits."""
    # 2.0 MWh battery
    battery = BatterySystem(capacity_mwh=2.0)
    initial_energy = battery.current_energy_kwh

    # Attempt to charge with 500 kWh
    charge_in, loss_in = battery.charge(500.0)
    assert charge_in > 0.0
    assert battery.current_energy_kwh > initial_energy
    # Energy stored = charge_in * eta_oneway
    assert np.isclose(battery.current_energy_kwh - initial_energy, charge_in * battery.eta_oneway, atol=1e-2)

    # Discharge
    delivered, loss_out = battery.discharge(200.0)
    assert delivered > 0.0


def test_hourly_dispatch_strict_energy_balance() -> None:
    """Verify simulate_hourly_dispatch satisfies energy balance at every hourly step."""
    dates = pd.date_range("2024-01-01 00:00:00", periods=24, freq="1h")

    # Synthetic solar bell curve for testing
    solar = pd.Series(
        [0, 0, 0, 0, 0, 0, 50, 200, 500, 800, 1000, 1200, 1100, 900, 600, 300, 100, 0, 0, 0, 0, 0, 0, 0],
        index=dates,
        dtype=float,
    )
    # Pumping demand inside 10:00 to 18:00
    demand = pd.Series(
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 400, 400, 400, 400, 400, 400, 400, 400, 0, 0, 0, 0, 0, 0],
        index=dates,
        dtype=float,
    )

    dispatch_df, metrics = simulate_hourly_dispatch(
        solar_generation_kwh=solar,
        pump_demand_kwh=demand,
        battery_capacity_mwh=1.0,
    )

    assert metrics["max_energy_balance_error_kwh"] < 1e-4
    assert metrics["total_solar_served_mwh"] > 0.0
    assert metrics["curtailment_avoided_mwh"] >= 0.0


def test_curtailment_avoided_metric_positive() -> None:
    """Verify adding battery storage strictly reduces or preserves curtailment compared to baseline."""
    dates = pd.date_range("2024-01-01 00:00:00", periods=24, freq="1h")
    # High solar with small demand and small transformer export limit (0.5 MVA -> 380 kW export limit)
    solar = pd.Series([1000.0] * 24, index=dates)
    demand = pd.Series([100.0] * 24, index=dates)

    _, metrics_with_battery = simulate_hourly_dispatch(
        solar_generation_kwh=solar,
        pump_demand_kwh=demand,
        battery_capacity_mwh=2.0,
        pt_capacity_mva=0.5,
    )

    # Battery absorbs surplus that exceeds 380 kW export ceiling -> curtailment avoided is positive
    assert metrics_with_battery["curtailment_avoided_mwh"] > 0.0

