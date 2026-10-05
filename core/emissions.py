"""CO2 emissions reduction calculations using regional CEA baseline factor.

Enforces PROJECT_SPEC Module 5:
Emissions: single line, avoided_kg = solar_energy_used_kwh * grid_emission_factor
(factor from config, with the named CEA version).
"""

from typing import Dict, Any

from core.config_loader import ConfigLoader, default_config_loader


def calculate_avoided_emissions(
    solar_energy_used_kwh: float,
    loader: ConfigLoader = default_config_loader,
) -> Dict[str, Any]:
    """Calculate annual greenhouse gas emissions avoided by solar energy generation.

    Formula:
    avoided_kg_co2 = solar_energy_used_kwh * grid_emission_factor_kg_co2_per_kwh
    """
    factor_entry = loader.get_assumption("grid_emission_factor_kg_co2_per_kwh")
    factor = float(factor_entry.value)
    source = factor_entry.source

    avoided_kg = solar_energy_used_kwh * factor
    avoided_tco2 = avoided_kg / 1000.0

    return {
        "solar_energy_used_kwh": round(solar_energy_used_kwh, 1),
        "solar_energy_used_mwh": round(solar_energy_used_kwh / 1000.0, 2),
        "grid_emission_factor_kg_per_kwh": factor,
        "grid_emission_factor_source": source,
        "baseline_version": source,
        "avoided_kg_co2": round(avoided_kg, 1),
        "avoided_t_co2": round(avoided_tco2, 2),
    }

