"""Unit tests for avoided carbon emissions and capacity optimization sweep."""

import numpy as np
import pandas as pd

from core.emissions import calculate_avoided_emissions
from core.solar.optimizer import run_capacity_optimization_sweep
from core.units import capital_recovery_factor


def test_calculate_avoided_emissions() -> None:
    """Verify avoided emissions matches formula: solar_kwh * emission_factor."""
    # 1,000,000 kWh solar energy used
    # Emission factor from config: CEA Version 20.0 = 0.716 kg CO2 / kWh
    res = calculate_avoided_emissions(1000000.0)
    assert np.isclose(res["avoided_kg_co2"], 716000.0, atol=1.0)
    assert np.isclose(res["avoided_t_co2"], 716.0, atol=1e-2)
    assert "CEA" in res["baseline_version"]


def test_calculate_residual_emissions_and_grid_dependence() -> None:
    """Verify residual grid dependence % and residual emissions calculations."""
    res = calculate_avoided_emissions(
        solar_energy_used_kwh=700000.0,
        grid_imported_kwh=300000.0,
        total_demand_kwh=1000000.0,
    )
    assert np.isclose(res["avoided_t_co2"], 501.2, atol=1e-2)
    assert np.isclose(res["residual_t_co2"], 214.8, atol=1e-2)
    assert np.isclose(res["residual_grid_dependence_pct"], 30.0, atol=1e-2)



def test_capital_recovery_factor_zero_discount() -> None:
    """Verify CRF handles zero discount rate cleanly (CRF = 1 / lifetime)."""
    crf = capital_recovery_factor(0.0, 25)
    assert np.isclose(crf, 1.0 / 25.0, atol=1e-5)


def test_capital_recovery_factor_hand_calc() -> None:
    """Verify CRF formula r*(1+r)^n / ((1+r)^n - 1) against analytical hand calculation."""
    # r = 0.08, n = 25
    # (1+0.08)^25 = 6.848475
    # CRF = 0.08 * 6.848475 / (5.848475) = 0.547878 / 5.848475 = 0.09367878
    crf = capital_recovery_factor(0.08, 25)
    assert np.isclose(crf, 0.09367878, atol=1e-5)


def test_optimizer_sweep_feasibility() -> None:
    """Verify optimizer sweep identifies feasible configurations and returns least-cost setup."""
    dates = pd.date_range("2024-01-01 00:00:00", periods=24, freq="1h")
    # Normalized solar curve (per kWp)
    solar_per_kwp = pd.Series([0.0]*8 + [0.3, 0.6, 0.8, 0.9, 0.8, 0.6, 0.3] + [0.0]*9, index=dates)
    # Demand series
    demand_kwh = pd.Series([0.0]*10 + [500.0]*8 + [0.0]*6, index=dates)

    sweep_df, best = run_capacity_optimization_sweep(
        solar_series_per_kwp=solar_per_kwp,
        demand_series_kwh=demand_kwh,
        target_solar_share=0.50,
    )

    assert isinstance(sweep_df, pd.DataFrame)
    assert len(sweep_df) > 0
    if best is not None:
        assert best["solar_share_percent"] >= 50.0


def test_optimizer_is_deterministic() -> None:
    """Verify optimizer returns identical results on repeated runs (no randomness)."""
    dates = pd.date_range("2024-01-01 00:00:00", periods=24, freq="1h")
    solar_per_kwp = pd.Series([0.0]*8 + [0.3, 0.6, 0.8, 0.9, 0.8, 0.6, 0.3] + [0.0]*9, index=dates)
    demand_kwh = pd.Series([0.0]*10 + [500.0]*8 + [0.0]*6, index=dates)

    df1, best1 = run_capacity_optimization_sweep(
        solar_series_per_kwp=solar_per_kwp,
        demand_series_kwh=demand_kwh,
        target_solar_share=0.50,
        solar_min_mwp=0.5,
        solar_max_mwp=1.5,
        solar_step_mwp=0.5,
        battery_min_mwh=0.0,
        battery_max_mwh=1.0,
        battery_step_mwh=1.0,
    )
    df2, best2 = run_capacity_optimization_sweep(
        solar_series_per_kwp=solar_per_kwp,
        demand_series_kwh=demand_kwh,
        target_solar_share=0.50,
        solar_min_mwp=0.5,
        solar_max_mwp=1.5,
        solar_step_mwp=0.5,
        battery_min_mwh=0.0,
        battery_max_mwh=1.0,
        battery_step_mwh=1.0,
    )

    pd.testing.assert_frame_equal(df1, df2)
    assert best1 == best2


def test_optimizer_resimulation_reproduces_target_share() -> None:
    """Verify minimum-cost configuration reproduces the target share when re-simulated."""
    from core.solar.dispatch import simulate_hourly_dispatch

    dates = pd.date_range("2024-01-01 00:00:00", periods=24, freq="1h")
    solar_per_kwp = pd.Series([0.0]*8 + [0.3, 0.6, 0.8, 0.9, 0.8, 0.6, 0.3] + [0.0]*9, index=dates)
    demand_kwh = pd.Series([0.0]*10 + [500.0]*8 + [0.0]*6, index=dates)

    target_share = 0.50
    _, best = run_capacity_optimization_sweep(
        solar_series_per_kwp=solar_per_kwp,
        demand_series_kwh=demand_kwh,
        target_solar_share=target_share,
        solar_min_mwp=0.5,
        solar_max_mwp=1.5,
        solar_step_mwp=0.5,
        battery_min_mwh=0.0,
        battery_max_mwh=1.0,
        battery_step_mwh=1.0,
    )

    assert best is not None
    # Re-simulate
    solar_kwh = solar_per_kwp * 1000.0 * best["solar_mwp"]
    _, metrics = simulate_hourly_dispatch(
        solar_kwh_series=solar_kwh,
        demand_kwh_series=demand_kwh,
        battery_capacity_mwh=best["battery_mwh"],
        pt_capacity_mva=5.0,
    )
    assert metrics["solar_share_percent"] >= target_share * 100.0 - 1e-4
    assert np.isclose(metrics["solar_share_percent"], best["solar_share_percent"], atol=1e-2)


def test_optimizer_unreachable_target_returns_message() -> None:
    """Verify unreachable target returns a clear generated message and best_config is None."""
    dates = pd.date_range("2024-01-01 00:00:00", periods=24, freq="1h")
    # Tiny solar, huge demand
    solar_per_kwp = pd.Series([0.0]*8 + [0.01]*8 + [0.0]*8, index=dates)
    demand_kwh = pd.Series([10000.0]*24, index=dates)

    df, best = run_capacity_optimization_sweep(
        solar_series_per_kwp=solar_per_kwp,
        demand_series_kwh=demand_kwh,
        target_solar_share=0.95,
        solar_min_mwp=0.5,
        solar_max_mwp=1.0,
        solar_step_mwp=0.5,
        battery_min_mwh=0.0,
        battery_max_mwh=0.0,
        battery_step_mwh=1.0,
    )

    assert best is None
    assert "unreachable_message" in df.attrs
    msg = df.attrs["unreachable_message"]
    assert "unreachable" in msg
    assert "95.0%" in msg


def test_inverse_command_area_monotonicity_and_reproduction() -> None:
    """Verify solar share strictly falls as command area rises, and reported area reproduces target."""
    from core.solar.optimizer import calculate_command_area_for_target_share
    from core.solar.dispatch import simulate_hourly_dispatch

    dates = pd.date_range("2024-01-01 00:00:00", periods=24, freq="1h")
    solar_kwh = pd.Series([0.0]*8 + [1000.0, 1500.0, 1800.0, 2000.0, 1800.0, 1500.0, 1000.0] + [0.0]*9, index=dates)
    base_demand = pd.Series([0.0]*10 + [400.0]*8 + [0.0]*6, index=dates)
    base_area_ha = 100.0

    # 1. Monotonicity check
    areas = [50.0, 100.0, 200.0]
    shares = []
    for a in areas:
        scale = a / base_area_ha
        _, m = simulate_hourly_dispatch(solar_kwh, base_demand * scale, battery_capacity_mwh=1.0)
        shares.append(m["solar_share_percent"])

    assert shares[0] > shares[1] > shares[2], "Solar share must strictly decrease as command area increases"

    # 2. Inverse calculation check
    target_share = 0.70
    res = calculate_command_area_for_target_share(
        base_demand_kwh_series=base_demand,
        solar_kwh_series=solar_kwh,
        base_command_area_ha=base_area_ha,
        target_solar_share=target_share,
        battery_capacity_mwh=1.0,
    )

    assert res["feasible"] is True
    found_area = res["command_area_ha"]
    assert found_area > 0

    # 3. Plug back in and verify reproduction of target share
    scale_back = found_area / base_area_ha
    _, m_back = simulate_hourly_dispatch(solar_kwh, base_demand * scale_back, battery_capacity_mwh=1.0)
    assert abs(m_back["solar_share_percent"] - target_share * 100.0) <= 0.2

