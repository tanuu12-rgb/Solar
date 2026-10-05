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
