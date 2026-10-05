"""Hydraulic and electrical agricultural water pump energy calculations.

Enforces PROJECT_SPEC Module 2 Item 7:
E_hyd_kwh = rho * g * H * V / 3.6e6
E_el_kwh = E_hyd_kwh / (eta_pump * eta_motor)
H = groundwater_depth_m + drawdown_m + friction_head_m
"""

import pandas as pd

from core.config_loader import ConfigLoader, default_config_loader
from core.units import RHO_WATER, G_ACCELERATION, JOULES_PER_KWH


def calculate_total_dynamic_head_m(loader: ConfigLoader = default_config_loader) -> float:
    """Calculate Total Dynamic Head (TDH) in meters from config assumptions."""
    gw_depth = float(loader.get_assumption_value("groundwater_depth_m"))
    drawdown = float(loader.get_assumption_value("drawdown_m"))
    friction = float(loader.get_assumption_value("friction_head_m"))
    return gw_depth + drawdown + friction


def calculate_pump_energy_from_volume(
    volume_m3: pd.Series | float,
    loader: ConfigLoader = default_config_loader,
) -> tuple[pd.Series | float, pd.Series | float]:
    """Calculate hydraulic energy (kWh) and electrical energy (kWh) for a given water volume (m³).

    Formulas:
    E_hyd_kwh = (rho * g * H * V) / 3.6e6
    E_el_kwh = E_hyd_kwh / (eta_pump * eta_motor)

    Returns:
    (hydraulic_energy_kwh, electrical_energy_kwh)
    """
    head_m = calculate_total_dynamic_head_m(loader)
    eta_pump = float(loader.get_assumption_value("pump_efficiency"))
    eta_motor = float(loader.get_assumption_value("motor_efficiency"))

    # rho * g * H * V / 3.6e6
    e_hyd_kwh = (RHO_WATER * G_ACCELERATION * head_m * volume_m3) / JOULES_PER_KWH
    combined_efficiency = eta_pump * eta_motor
    e_el_kwh = e_hyd_kwh / combined_efficiency

    return e_hyd_kwh, e_el_kwh
