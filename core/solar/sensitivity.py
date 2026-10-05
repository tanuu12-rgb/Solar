"""One-at-a-time (OAT) sensitivity analysis for solarization planning.

Enforces PROJECT_SPEC Module 5:
One-at-a-time sensitivity (solar capacity, battery capacity, crop area, capex, tariff)
as a tornado chart dataset.
"""

from typing import Dict, Any, List, Optional
import pandas as pd

from core.config_loader import ConfigLoader, default_config_loader
from core.solar.dispatch import simulate_hourly_dispatch
from core.solar.optimizer import calculate_annualized_system_cost


def run_oat_sensitivity_analysis(
    base_solar_kwh_series: pd.Series,
    base_demand_kwh_series: pd.Series,
    base_solar_capacity_mwp: float,
    base_battery_capacity_mwh: float,
    variation_pct: float = 20.0,
    loader: ConfigLoader = default_config_loader,
) -> pd.DataFrame:
    """Run One-at-a-time (OAT) sensitivity analysis varying key parameters by +/- variation_pct."""
    var_factor_low = 1.0 - (variation_pct / 100.0)
    var_factor_high = 1.0 + (variation_pct / 100.0)

    # Base dispatch
    _, base_metrics = simulate_hourly_dispatch(
        solar_kwh_series=base_solar_kwh_series,
        demand_kwh_series=base_demand_kwh_series,
        battery_capacity_mwh=base_battery_capacity_mwh,
        loader=loader,
    )
    base_costs = calculate_annualized_system_cost(
        solar_capacity_mwp=base_solar_capacity_mwp,
        battery_capacity_mwh=base_battery_capacity_mwh,
        grid_imported_kwh=base_metrics["grid_imported_mwh"] * 1000.0,
        loader=loader,
    )
    base_cost_val = base_costs["total_annual_cost_inr"]
    solar_served_base = base_metrics["total_solar_served_mwh"] * 1000.0
    base_unit_cost = base_cost_val / solar_served_base if solar_served_base > 0 else 0.0

    parameters = [
        "Solar Capex",
        "Battery Capex",
        "Grid Tariff",
        "Irrigation Demand",
        "Solar Generation",
    ]

    records = []

    for param in parameters:
        for direction, factor in [("low", var_factor_low), ("high", var_factor_high)]:
            if param == "Solar Capex":
                mod_costs = calculate_annualized_system_cost(
                    solar_capacity_mwp=base_solar_capacity_mwp,
                    battery_capacity_mwh=base_battery_capacity_mwh,
                    grid_imported_kwh=base_metrics["grid_imported_mwh"] * 1000.0,
                    loader=loader,
                )
                crf_proj = mod_costs["annual_solar_capex_inr"]
                delta_capex = (factor - 1.0) * crf_proj
                cost = base_cost_val + delta_capex
                solar_share = base_metrics["solar_share_percent"]
                served = solar_served_base

            elif param == "Battery Capex":
                mod_costs = calculate_annualized_system_cost(
                    solar_capacity_mwp=base_solar_capacity_mwp,
                    battery_capacity_mwh=base_battery_capacity_mwh,
                    grid_imported_kwh=base_metrics["grid_imported_mwh"] * 1000.0,
                    loader=loader,
                )
                crf_batt = mod_costs["annual_battery_capex_inr"]
                delta_capex = (factor - 1.0) * crf_batt
                cost = base_cost_val + delta_capex
                solar_share = base_metrics["solar_share_percent"]
                served = solar_served_base

            elif param == "Grid Tariff":
                orig_grid_cost = base_costs["annual_grid_cost_inr"]
                delta_grid = (factor - 1.0) * orig_grid_cost
                cost = base_cost_val + delta_grid
                solar_share = base_metrics["solar_share_percent"]
                served = solar_served_base

            elif param == "Irrigation Demand":
                mod_demand = base_demand_kwh_series * factor
                _, m_sens = simulate_hourly_dispatch(
                    solar_kwh_series=base_solar_kwh_series,
                    demand_kwh_series=mod_demand,
                    battery_capacity_mwh=base_battery_capacity_mwh,
                    loader=loader,
                )
                c_sens = calculate_annualized_system_cost(
                    solar_capacity_mwp=base_solar_capacity_mwp,
                    battery_capacity_mwh=base_battery_capacity_mwh,
                    grid_imported_kwh=m_sens["grid_imported_mwh"] * 1000.0,
                    loader=loader,
                )
                cost = c_sens["total_annual_cost_inr"]
                solar_share = m_sens["solar_share_percent"]
                served = m_sens["total_solar_served_mwh"] * 1000.0

            elif param == "Solar Generation":
                mod_solar = base_solar_kwh_series * factor
                _, m_sens = simulate_hourly_dispatch(
                    solar_kwh_series=mod_solar,
                    demand_kwh_series=base_demand_kwh_series,
                    battery_capacity_mwh=base_battery_capacity_mwh,
                    loader=loader,
                )
                c_sens = calculate_annualized_system_cost(
                    solar_capacity_mwp=base_solar_capacity_mwp,
                    battery_capacity_mwh=base_battery_capacity_mwh,
                    grid_imported_kwh=m_sens["grid_imported_mwh"] * 1000.0,
                    loader=loader,
                )
                cost = c_sens["total_annual_cost_inr"]
                solar_share = m_sens["solar_share_percent"]
                served = m_sens["total_solar_served_mwh"] * 1000.0

            cost_delta_pct = ((cost - base_cost_val) / base_cost_val) * 100.0
            unit_cost = cost / served if served > 0 else 0.0

            records.append({
                "parameter": param,
                "variation": direction,
                "factor": factor,
                "annual_cost_inr": round(cost, 2),
                "unit_cost_inr_per_kwh": round(unit_cost, 2),
                "cost_delta_percent": round(cost_delta_pct, 2),
                "solar_share_percent": round(solar_share, 2),
            })

    return pd.DataFrame(records)


def run_tornado_sensitivity(
    base_solar_mwp: float,
    base_battery_mwh: float,
    base_demand_series_kwh: pd.Series,
    solar_generation_per_kwp: pd.Series,
    variation_pct: float = 20.0,
    loader: ConfigLoader = default_config_loader,
) -> pd.DataFrame:
    """Generate wide-format tornado dataset for dashboard visualization."""
    solar_kwh = solar_generation_per_kwp * (base_solar_mwp * 1000.0)
    raw_df = run_oat_sensitivity_analysis(
        base_solar_kwh_series=solar_kwh,
        base_demand_kwh_series=base_demand_series_kwh,
        base_solar_capacity_mwp=base_solar_mwp,
        base_battery_capacity_mwh=base_battery_mwh,
        variation_pct=variation_pct,
        loader=loader,
    )

    # Compute base unit cost
    _, base_m = simulate_hourly_dispatch(
        solar_kwh_series=solar_kwh,
        demand_kwh_series=base_demand_series_kwh,
        battery_capacity_mwh=base_battery_mwh,
        loader=loader,
    )
    base_costs = calculate_annualized_system_cost(
        solar_capacity_mwp=base_solar_mwp,
        battery_capacity_mwh=base_battery_mwh,
        grid_imported_kwh=base_m["grid_imported_mwh"] * 1000.0,
        loader=loader,
    )
    solar_served_base = base_m["total_solar_served_mwh"] * 1000.0
    base_cost_per_kwh = base_costs["total_annual_cost_inr"] / solar_served_base if solar_served_base > 0 else 0.0

    rows = []
    for param in raw_df["parameter"].unique():
        sub = raw_df[raw_df["parameter"] == param]
        low_row = sub[sub["variation"] == "low"].iloc[0]
        high_row = sub[sub["variation"] == "high"].iloc[0]
        rows.append({
            "parameter": param,
            "base_cost_inr": round(base_cost_per_kwh, 2),
            "low_cost_inr": round(low_row["unit_cost_inr_per_kwh"], 2),
            "high_cost_inr": round(high_row["unit_cost_inr_per_kwh"], 2),
            "spread_inr": abs(round(high_row["unit_cost_inr_per_kwh"] - low_row["unit_cost_inr_per_kwh"], 2)),
        })

    tornado_df = pd.DataFrame(rows).sort_values("spread_inr", ascending=True)
    return tornado_df
