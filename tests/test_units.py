"""Unit tests for physical constants and unit conversion functions.

Cites hand calculations per PROJECT_SPEC Section 7.
"""

import pytest
from core.units import (
    GRAVITY_ACCELERATION_M_S2,
    WATER_DENSITY_KG_M3,
    depth_mm_and_area_ha_to_volume_m3,
    hydraulic_energy_kwh,
    electrical_pump_energy_kwh,
    mva_to_kw,
)


def test_physical_constants() -> None:
    """Verify standard physical constants (g = 9.81 m/s², rho = 1000 kg/m³)."""
    assert GRAVITY_ACCELERATION_M_S2 == 9.81
    assert WATER_DENSITY_KG_M3 == 1000.0


def test_depth_and_area_to_volume() -> None:
    """Verify volume calculation: V_m3 = depth_mm * 10 * area_ha.

    Hand calculation:
    1 mm over 1 ha (10,000 m²) is 0.001 m * 10,000 m² = 10 m³.
    For 5.0 mm over 20.0 ha: V = 5.0 * 10 * 20.0 = 1000.0 m³.
    """
    assert depth_mm_and_area_ha_to_volume_m3(5.0, 20.0) == 1000.0
    assert depth_mm_and_area_ha_to_volume_m3(0.0, 20.0) == 0.0

    with pytest.raises(ValueError, match="depth_mm cannot be negative"):
        depth_mm_and_area_ha_to_volume_m3(-1.0, 10.0)

    with pytest.raises(ValueError, match="area_ha cannot be negative"):
        depth_mm_and_area_ha_to_volume_m3(5.0, -10.0)


def test_hydraulic_energy_hand_calculation() -> None:
    """Verify hydraulic energy calculation: E_hyd = rho * g * H * V / 3.6e6.

    Hand calculation:
    rho = 1000 kg/m³, g = 9.81 m/s², H = 50.0 m, V = 1000.0 m³.
    E_hyd = (1000 * 9.81 * 50 * 1000) / 3,600,000
          = 490,500,000 J / 3,600,000 J/kWh
          = 136.25 kWh exactly.
    """
    result = hydraulic_energy_kwh(volume_m3=1000.0, head_m=50.0)
    assert abs(result - 136.25) < 1e-9

    with pytest.raises(ValueError, match="volume_m3 cannot be negative"):
        hydraulic_energy_kwh(-10.0, 50.0)

    with pytest.raises(ValueError, match="head_m cannot be negative"):
        hydraulic_energy_kwh(100.0, -5.0)


def test_electrical_pump_energy_hand_calculation() -> None:
    """Verify electrical pump energy: E_el = E_hyd / (eta_pump * eta_motor).

    Hand calculation:
    E_hyd = 136.25 kWh.
    eta_pump = 0.70, eta_motor = 0.85 -> product = 0.595.
    E_el = 136.25 / 0.595 = 228.99159663865545 kWh.
    """
    result = electrical_pump_energy_kwh(
        hydraulic_energy_kwh_val=136.25,
        pump_efficiency=0.70,
        motor_efficiency=0.85,
    )
    expected = 136.25 / 0.595
    assert abs(result - expected) < 1e-9

    with pytest.raises(ValueError, match="pump_efficiency must be in"):
        electrical_pump_energy_kwh(100.0, 0.0, 0.85)

    with pytest.raises(ValueError, match="motor_efficiency must be in"):
        electrical_pump_energy_kwh(100.0, 0.70, 1.2)


def test_mva_to_kw() -> None:
    """Verify transformer apparent power conversion to active power.

    Hand calculation:
    5.0 MVA at 0.90 power factor = 5.0 * 1000 * 0.90 = 4500.0 kW.
    """
    result = mva_to_kw(5.0, 0.90)
    assert result == 4500.0

    with pytest.raises(ValueError, match="capacity_mva cannot be negative"):
        mva_to_kw(-1.0, 0.9)

    with pytest.raises(ValueError, match="power_factor must be in"):
        mva_to_kw(5.0, 1.5)
