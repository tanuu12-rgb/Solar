"""CO2 emissions reduction calculations using regional CEA baseline factor.

Enforces PROJECT_SPEC Module 5 & Phase 5:
- Avoided emissions: avoided_kg = solar_energy_used_kwh * grid_emission_factor
- Residual emissions: residual_kg = grid_imported_kwh * grid_emission_factor
- Residual grid dependence: % of annual irrigation energy supplied by grid.
"""

from typing import Dict, Any, Optional

from core.config_loader import ConfigLoader, default_config_loader
from core.errors import MissingInputError


def calculate_avoided_emissions(
    solar_energy_used_kwh: float,
    grid_imported_kwh: Optional[float] = None,
    total_demand_kwh: Optional[float] = None,
    loader: ConfigLoader = default_config_loader,
) -> Dict[str, Any]:
    """Calculate annual GHG emissions avoided and residual emissions from grid dependence.

    Formula:
    avoided_kg_co2 = solar_energy_used_kwh * grid_emission_factor_kg_co2_per_kwh
    residual_kg_co2 = grid_imported_kwh * grid_emission_factor_kg_co2_per_kwh
    """
    factor_entry = loader.get_assumption("grid_emission_factor_kg_co2_per_kwh")
    if factor_entry.value is None:
        raise MissingInputError(
            "grid_emission_factor_kg_co2_per_kwh",
            "CEA grid emission factor not populated in config/assumptions.yaml",
        )

    factor = float(factor_entry.value)
    source = factor_entry.source

    avoided_kg = solar_energy_used_kwh * factor
    avoided_tco2 = avoided_kg / 1000.0

    res = {
        "solar_energy_used_kwh": round(solar_energy_used_kwh, 1),
        "solar_energy_used_mwh": round(solar_energy_used_kwh / 1000.0, 2),
        "grid_emission_factor_kg_per_kwh": factor,
        "grid_emission_factor_source": source,
        "baseline_version": source,
        "avoided_kg_co2": round(avoided_kg, 1),
        "avoided_t_co2": round(avoided_tco2, 2),
    }

    if grid_imported_kwh is not None:
        residual_kg = grid_imported_kwh * factor
        residual_tco2 = residual_kg / 1000.0
        res["grid_imported_kwh"] = round(grid_imported_kwh, 1)
        res["grid_imported_mwh"] = round(grid_imported_kwh / 1000.0, 2)
        res["residual_kg_co2"] = round(residual_kg, 1)
        res["residual_t_co2"] = round(residual_tco2, 2)

    if total_demand_kwh is not None and total_demand_kwh > 0:
        res["total_demand_kwh"] = round(total_demand_kwh, 1)
        res["total_demand_mwh"] = round(total_demand_kwh / 1000.0, 2)
        if grid_imported_kwh is not None:
            grid_dep_pct = (grid_imported_kwh / total_demand_kwh) * 100.0
            res["residual_grid_dependence_pct"] = round(grid_dep_pct, 2)

    return res


def calculate_residual_grid_emissions(
    grid_imported_kwh: float,
    loader: ConfigLoader = default_config_loader,
) -> float:
    """Calculate annual residual emissions (tCO2) from grid electricity consumption."""
    factor_entry = loader.get_assumption("grid_emission_factor_kg_co2_per_kwh")
    factor = float(factor_entry.value) if factor_entry.value is not None else 0.82
    return round((grid_imported_kwh * factor) / 1000.0, 2)


def calculate_residual_grid_dependence(
    grid_imported_kwh: float,
    total_demand_kwh: float,
) -> float:
    """Calculate the percentage of annual irrigation energy supplied by the grid."""
    if total_demand_kwh <= 0:
        return 0.0
    return round((grid_imported_kwh / total_demand_kwh) * 100.0, 2)

