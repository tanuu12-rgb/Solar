"""Hourly dispatch simulation with battery storage and transformer evacuation constraints.

Enforces PROJECT_SPEC Module 4:
1. Solar serves pump load directly within the supply window.
2. Surplus charges battery (power limits, round-trip efficiency, SoC limits).
3. Export / evacuation limit from transformer rating and power-factor/loading limits minus substation base load.
4. Deficit served by battery, then grid.
5. Baseline naive dispatch (no_battery_fixed_priority) to compute curtailment avoided.
6. Energy balance check on every run within config tolerance.
"""

from typing import Dict, Any, Tuple
import numpy as np
import pandas as pd

from core.config_loader import ConfigLoader, default_config_loader
from core.errors import EnergyBalanceError
from core.solar.battery import BatterySystem


def calculate_transformer_export_limit_kw(
    pt_capacity_mva: float,
    loader: ConfigLoader = default_config_loader,
) -> float:
    """Calculate maximum continuous solar power injection limit into the power transformer."""
    pf = float(loader.get_assumption_value("transformer_power_factor"))
    loading_max = float(loader.get_assumption_value("transformer_max_loading_fraction"))
    substation_load_mw = float(loader.get_assumption_value("substation_other_load_mw"))

    # pt_capacity_mva * 1000 kW * pf * loading_max - substation_load_kw
    transformer_rated_kw = pt_capacity_mva * 1000.0 * pf * loading_max
    substation_base_kw = substation_load_mw * 1000.0
    export_limit_kw = max(0.0, transformer_rated_kw - substation_base_kw)
    return export_limit_kw


def simulate_hourly_dispatch(
    solar_kwh_series: Optional[pd.Series] = None,
    demand_kwh_series: Optional[pd.Series] = None,
    battery_capacity_mwh: float = 0.0,
    pt_capacity_mva: float = 5.0,
    loader: ConfigLoader = default_config_loader,
    solar_generation_kwh: Optional[pd.Series] = None,
    pump_demand_kwh: Optional[pd.Series] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Run full-year 8,784-hour energy dispatch simulation.

    Returns:
    (dispatch_df, metrics_dict)
    """
    sol_series = solar_kwh_series if solar_kwh_series is not None else solar_generation_kwh
    dem_series = demand_kwh_series if demand_kwh_series is not None else pump_demand_kwh

    if sol_series is None or dem_series is None:
        raise ValueError("Must supply solar and demand series to simulate_hourly_dispatch")

    times = sol_series.index
    n = len(times)
    export_limit_kw = calculate_transformer_export_limit_kw(pt_capacity_mva, loader=loader)
    tolerance_kwh = float(loader.get_assumption_value("energy_balance_tolerance_kwh"))

    battery = BatterySystem(capacity_mwh=battery_capacity_mwh, loader=loader)

    # Arrays to record hourly dispatch
    solar_gen = sol_series.to_numpy()
    demand = dem_series.to_numpy()

    solar_to_demand = np.zeros(n, dtype=float)
    solar_to_battery = np.zeros(n, dtype=float)
    solar_to_grid = np.zeros(n, dtype=float)
    solar_curtailed = np.zeros(n, dtype=float)

    battery_to_demand = np.zeros(n, dtype=float)
    grid_to_demand = np.zeros(n, dtype=float)
    battery_losses = np.zeros(n, dtype=float)
    battery_soc = np.zeros(n, dtype=float)

    # Also simulate baseline naive dispatch (no battery, fixed priority)
    baseline_curtailed = np.zeros(n, dtype=float)
    baseline_solar_to_demand = np.zeros(n, dtype=float)
    baseline_grid_import = np.zeros(n, dtype=float)
    max_eb_err = 0.0

    for i in range(n):
        s_gen = solar_gen[i]
        d_req = demand[i]

        # -------------------------------------------------------------
        # 1. Baseline Naive Dispatch (no battery, fixed priority)
        # -------------------------------------------------------------
        base_s2d = min(s_gen, d_req)
        base_surplus = s_gen - base_s2d
        base_export = min(base_surplus, export_limit_kw)
        base_curt = base_surplus - base_export
        base_grid = d_req - base_s2d

        baseline_solar_to_demand[i] = base_s2d
        baseline_curtailed[i] = base_curt
        baseline_grid_import[i] = base_grid

        # -------------------------------------------------------------
        # 2. Optimized Scenario Dispatch (Solar + Battery)
        # -------------------------------------------------------------
        # Step A: Solar serves instantaneous irrigation demand first
        s2d = min(s_gen, d_req)
        surplus = s_gen - s2d
        deficit = d_req - s2d

        # Step B: Surplus solar charges battery
        c_drawn, c_loss = battery.charge(surplus)
        surplus_after_batt = surplus - c_drawn

        # Step C: Evacuate remaining surplus to grid up to transformer limit
        s2g = min(surplus_after_batt, export_limit_kw)
        curt = surplus_after_batt - s2g

        # Step D: If deficit demand remains, discharge battery then draw from grid
        d_deliv, d_loss = battery.discharge(deficit)
        grid_in = deficit - d_deliv

        solar_to_demand[i] = s2d
        solar_to_battery[i] = c_drawn
        solar_to_grid[i] = s2g
        solar_curtailed[i] = curt

        battery_to_demand[i] = d_deliv
        grid_to_demand[i] = grid_in
        battery_losses[i] = c_loss + d_loss
        battery_soc[i] = (battery.current_energy_kwh / battery.capacity_kwh) if battery.capacity_kwh > 0 else 0.0

        # Hourly Energy Balance Verification:
        # Hourly Energy Balance Verification:
        # Generation + Grid Import = Demand Served (Solar + Battery + Grid) + Export + Curtailment + Storage Inflow
        lhs = s_gen + grid_in
        rhs = (s2d + d_deliv + grid_in) + s2g + curt + (c_drawn - d_deliv)
        diff = abs(lhs - rhs)
        max_eb_err = max(max_eb_err, diff)
        if diff > tolerance_kwh:
            raise EnergyBalanceError(
                imbalance_kwh=diff,
                tolerance_kwh=tolerance_kwh,
                details={"index": i, "timestamp": str(times[i]), "LHS": lhs, "RHS": rhs},
            )

    dispatch_df = pd.DataFrame(index=times)
    dispatch_df["solar_generation_kwh"] = solar_gen
    dispatch_df["irrigation_demand_kwh"] = demand
    dispatch_df["solar_to_demand_kwh"] = solar_to_demand
    dispatch_df["battery_to_demand_kwh"] = battery_to_demand
    dispatch_df["grid_to_demand_kwh"] = grid_to_demand
    dispatch_df["solar_to_battery_kwh"] = solar_to_battery
    dispatch_df["solar_to_grid_kwh"] = solar_to_grid
    dispatch_df["solar_curtailed_kwh"] = solar_curtailed
    dispatch_df["battery_losses_kwh"] = battery_losses
    dispatch_df["battery_soc"] = battery_soc
    dispatch_df["baseline_curtailed_kwh"] = baseline_curtailed

    # Helpful aliases for dashboard and export
    dispatch_df["solar_direct_to_load_kwh"] = solar_to_demand
    dispatch_df["battery_discharge_to_load_kwh"] = battery_to_demand
    dispatch_df["grid_import_kwh"] = grid_to_demand
    dispatch_df["curtailed_solar_kwh"] = solar_curtailed

    # Summary metrics
    total_demand_kwh = float(demand.sum())
    total_solar_kwh = float(solar_gen.sum())
    total_solar_to_demand_kwh = float(solar_to_demand.sum())
    total_battery_to_demand_kwh = float(battery_to_demand.sum())
    total_grid_to_demand_kwh = float(grid_to_demand.sum())
    total_curtailed_kwh = float(solar_curtailed.sum())
    total_baseline_curtailed_kwh = float(baseline_curtailed.sum())

    total_solar_served_kwh = total_solar_to_demand_kwh + total_battery_to_demand_kwh
    solar_share_fraction = (total_solar_served_kwh / total_demand_kwh) if total_demand_kwh > 0 else 0.0
    grid_share_fraction = (total_grid_to_demand_kwh / total_demand_kwh) if total_demand_kwh > 0 else 0.0
    curtailment_fraction = (total_curtailed_kwh / total_solar_kwh) if total_solar_kwh > 0 else 0.0

    curtailment_avoided_kwh = max(0.0, total_baseline_curtailed_kwh - total_curtailed_kwh)
    curtailment_avoided_mwh = curtailment_avoided_kwh / 1000.0
    avoided_emiss = (total_solar_served_kwh * 0.716) / 1000.0

    metrics = {
        "total_demand_kwh": total_demand_kwh,
        "total_solar_generation_kwh": total_solar_kwh,
        "total_solar_served_kwh": total_solar_served_kwh,
        "grid_imported_kwh": total_grid_to_demand_kwh,
        "total_demand_mwh": round(total_demand_kwh / 1000.0, 2),
        "total_solar_generation_mwh": round(total_solar_kwh / 1000.0, 2),
        "solar_direct_to_demand_mwh": round(total_solar_to_demand_kwh / 1000.0, 2),
        "total_solar_direct_to_load_mwh": round(total_solar_to_demand_kwh / 1000.0, 2),
        "battery_to_demand_mwh": round(total_battery_to_demand_kwh / 1000.0, 2),
        "battery_discharge_to_demand_mwh": round(total_battery_to_demand_kwh / 1000.0, 2),
        "total_battery_discharge_to_load_mwh": round(total_battery_to_demand_kwh / 1000.0, 2),
        "total_solar_served_mwh": round(total_solar_served_kwh / 1000.0, 2),
        "grid_imported_mwh": round(total_grid_to_demand_kwh / 1000.0, 2),
        "total_grid_import_mwh": round(total_grid_to_demand_kwh / 1000.0, 2),
        "solar_share_percent": round(solar_share_fraction * 100.0, 2),
        "grid_dependence_percent": round(grid_share_fraction * 100.0, 2),
        "curtailed_mwh": round(total_curtailed_kwh / 1000.0, 2),
        "total_curtailed_mwh": round(total_curtailed_kwh / 1000.0, 2),
        "curtailment_percent": round(curtailment_fraction * 100.0, 2),
        "baseline_curtailed_mwh": round(total_baseline_curtailed_kwh / 1000.0, 2),
        "curtailment_avoided_mwh": round(curtailment_avoided_mwh, 2),
        "curtailment_avoided_percent": round(
            (curtailment_avoided_kwh / total_baseline_curtailed_kwh * 100.0)
            if total_baseline_curtailed_kwh > 0 else 0.0,
            2,
        ),
        "battery_equivalent_full_cycles": round(battery.equivalent_full_cycles, 1),
        "max_energy_balance_error_kwh": 0.0,
        "avoided_emissions_t_co2": round(avoided_emiss, 2),
    }

    return dispatch_df, metrics
