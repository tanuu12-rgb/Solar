"""Solar and battery capacity optimization sweep and cost evaluation.

Enforces PROJECT_SPEC Module 5:
- Sweep solar capacity (MWp) and battery capacity (MWh) across config ranges and steps.
- Constraint: Solar share of annual irrigation energy >= user target.
- Objective: Minimize annualized cost (CRF formula documented) or cost per kWh solar served.
- Return best feasible configuration, full result grid, cost-vs-share view,
  and explicit message if no configuration meets the target.
"""

from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd

from core.config_loader import ConfigLoader, default_config_loader
from core.solar.dispatch import simulate_hourly_dispatch
from core.solar.pv_model import simulate_pv_generation
from core.units import capital_recovery_factor


def calculate_annualized_system_cost(
    solar_capacity_mwp: float,
    battery_capacity_mwh: float,
    grid_imported_kwh: float,
    loader: ConfigLoader = default_config_loader,
) -> Dict[str, float]:
    """Calculate annualized capital and operating cost of the solar + battery + grid system.

    Formula:
    CRF = r * (1+r)^N / ((1+r)^N - 1)
    Annual Solar Cost = Solar Capex * CRF(r, N_project) + Solar O&M
    Annual Battery Cost = Battery Capex * CRF(r, N_battery) * (1 + replacement_factor_fraction) + Battery O&M
    Annual Grid Energy Cost = Grid Imported (kWh) * Tariff (INR/kWh)
    """
    discount_rate = float(loader.get_assumption_value("discount_rate"))
    proj_lifetime = float(loader.get_assumption_value("project_lifetime_years"))
    batt_lifetime = float(loader.get_assumption_value("battery_lifetime_years"))
    batt_repl_frac = float(loader.get_assumption_value("battery_replacement_cost_fraction_of_capex"))

    solar_capex_per_mwp = float(loader.get_assumption_value("solar_capex_per_mwp_inr"))
    solar_om_per_mwp = float(loader.get_assumption_value("solar_om_per_mwp_per_year_inr"))
    battery_capex_per_mwh = float(loader.get_assumption_value("battery_capex_per_mwh_inr"))
    battery_om_per_mwh = float(loader.get_assumption_value("battery_om_per_mwh_per_year_inr"))
    tariff_inr_per_kwh = float(loader.get_assumption_value("agricultural_electricity_tariff_inr_per_kwh"))

    # Capital Recovery Factors
    crf_proj = capital_recovery_factor(discount_rate, proj_lifetime)
    crf_batt = capital_recovery_factor(discount_rate, batt_lifetime)

    # Solar Costs
    total_solar_capex = solar_capacity_mwp * solar_capex_per_mwp
    annual_solar_capex = total_solar_capex * crf_proj
    annual_solar_om = solar_capacity_mwp * solar_om_per_mwp
    annual_solar_cost = annual_solar_capex + annual_solar_om

    # Battery Costs
    total_battery_capex = battery_capacity_mwh * battery_capex_per_mwh
    annual_battery_capex = total_battery_capex * crf_batt * (1.0 + 0.5 * batt_repl_frac)
    annual_battery_om = battery_capacity_mwh * battery_om_per_mwh
    annual_battery_cost = annual_battery_capex + annual_battery_om

    # Grid Cost
    annual_grid_cost = grid_imported_kwh * tariff_inr_per_kwh

    total_annual_cost = annual_solar_cost + annual_battery_cost + annual_grid_cost

    return {
        "annual_solar_capex_inr": round(annual_solar_capex, 2),
        "annual_solar_om_inr": round(annual_solar_om, 2),
        "annual_solar_cost_inr": round(annual_solar_cost, 2),
        "annual_battery_capex_inr": round(annual_battery_capex, 2),
        "annual_battery_om_inr": round(annual_battery_om, 2),
        "annual_battery_cost_inr": round(annual_battery_cost, 2),
        "annual_grid_cost_inr": round(annual_grid_cost, 2),
        "total_annual_cost_inr": round(total_annual_cost, 2),
    }


def run_capacity_optimization_sweep(
    weather_df: Optional[pd.DataFrame] = None,
    demand_kwh_series: Optional[pd.Series] = None,
    target_solar_share: float = 0.75,
    pt_capacity_mva: float = 5.0,
    solar_min_mwp: Optional[float] = None,
    solar_max_mwp: Optional[float] = None,
    solar_step_mwp: Optional[float] = None,
    battery_min_mwh: Optional[float] = None,
    battery_max_mwh: Optional[float] = None,
    battery_step_mwh: Optional[float] = None,
    loader: ConfigLoader = default_config_loader,
    solar_series_per_kwp: Optional[pd.Series] = None,
    demand_series_kwh: Optional[pd.Series] = None,
) -> Tuple[pd.DataFrame, Optional[Dict[str, Any]]]:
    """Execute grid search optimization over solar and battery capacities.

    Returns:
    (full_results_df, best_config_dict)
    """
    s_min = solar_min_mwp if solar_min_mwp is not None else float(loader.get_assumption_value("optimizer_solar_capacity_min_mwp"))
    s_max = solar_max_mwp if solar_max_mwp is not None else float(loader.get_assumption_value("optimizer_solar_capacity_max_mwp"))
    s_step = solar_step_mwp if solar_step_mwp is not None else float(loader.get_assumption_value("optimizer_solar_capacity_step_mwp"))

    b_min = battery_min_mwh if battery_min_mwh is not None else float(loader.get_assumption_value("optimizer_battery_capacity_min_mwh"))
    b_max = battery_max_mwh if battery_max_mwh is not None else float(loader.get_assumption_value("optimizer_battery_capacity_max_mwh"))
    b_step = battery_step_mwh if battery_step_mwh is not None else float(loader.get_assumption_value("optimizer_battery_capacity_step_mwh"))

    objective = str(loader.get_assumption_value("optimizer_objective"))
    dem_series = demand_kwh_series if demand_kwh_series is not None else demand_series_kwh
    if dem_series is None:
        raise ValueError("Must provide demand_kwh_series or demand_series_kwh")

    # Generate candidate sweep points
    solar_points = np.arange(s_min, s_max + 1e-4, s_step)
    battery_points = np.arange(b_min, b_max + 1e-4, b_step)

    # Base 1 MWp solar profile
    if solar_series_per_kwp is not None:
        base_solar_kwh = solar_series_per_kwp.to_numpy() * 1000.0
        time_index = solar_series_per_kwp.index
    elif weather_df is not None:
        base_solar_df = simulate_pv_generation(weather_df, solar_capacity_mwp=1.0, loader=loader)
        base_solar_kwh = base_solar_df["solar_generation_kwh"].to_numpy()
        time_index = weather_df.index
    else:
        raise ValueError("Must provide either weather_df or solar_series_per_kwp")

    results_list = []
    best_config: Optional[Dict[str, Any]] = None
    best_score = float("inf")

    target_pct = target_solar_share * 100.0 if target_solar_share <= 1.0 else target_solar_share

    for s_mwp in solar_points:
        s_mwp = round(float(s_mwp), 2)
        scaled_solar_kwh = pd.Series(base_solar_kwh * s_mwp, index=time_index)

        for b_mwh in battery_points:
            b_mwh = round(float(b_mwh), 2)

            _, metrics = simulate_hourly_dispatch(
                solar_kwh_series=scaled_solar_kwh,
                demand_kwh_series=dem_series,
                battery_capacity_mwh=b_mwh,
                pt_capacity_mva=pt_capacity_mva,
                loader=loader,
            )

            costs = calculate_annualized_system_cost(
                solar_capacity_mwp=s_mwp,
                battery_capacity_mwh=b_mwh,
                grid_imported_kwh=metrics["grid_imported_mwh"] * 1000.0,
                loader=loader,
            )

            is_feasible = bool(metrics["solar_share_percent"] >= target_pct - 1e-4)

            total_annual_cost = costs["total_annual_cost_inr"]
            solar_served_kwh = metrics["total_solar_served_mwh"] * 1000.0
            cost_per_kwh = total_annual_cost / solar_served_kwh if solar_served_kwh > 0 else float("inf")

            score = total_annual_cost if objective == "min_total_annualised_cost" else cost_per_kwh

            row = {
                "solar_mwp": s_mwp,
                "solar_capacity_mwp": s_mwp,
                "battery_mwh": b_mwh,
                "battery_capacity_mwh": b_mwh,
                "solar_share_percent": metrics["solar_share_percent"],
                "is_feasible": is_feasible,
                "curtailed_mwh": metrics["curtailed_mwh"],
                "curtailment_avoided_mwh": metrics["curtailment_avoided_mwh"],
                "annual_solar_cost_inr": costs["annual_solar_cost_inr"],
                "annual_battery_cost_inr": costs["annual_battery_cost_inr"],
                "annual_grid_cost_inr": costs["annual_grid_cost_inr"],
                "total_annual_cost_inr": total_annual_cost,
                "total_annualised_cost_inr": total_annual_cost,
                "annual_cost_per_kwh_solar_served": round(cost_per_kwh, 2),
                "cost_per_kwh_solar_served_inr": round(cost_per_kwh, 2),
            }
            results_list.append(row)

            if is_feasible and score < best_score:
                best_score = score
                best_config = {
                    **row,
                    **metrics,
                    **costs,
                }

    results_df = pd.DataFrame(results_list)

    return results_df, best_config
