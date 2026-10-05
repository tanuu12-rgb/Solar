"""Physical and mathematical constants and conversion utilities.

Follows PROJECT_SPEC Section 0 Rule 2 (permitted mathematical/physical constants)
and Section 0 Rule 5 (strict naming convention with explicit units).
"""

# Physical constants (permitted exceptions under Section 0 Rule 2)
GRAVITY_ACCELERATION_M_S2: float = 9.81  # Standard acceleration due to gravity (m/s²)
WATER_DENSITY_KG_M3: float = 1000.0  # Pure water density at standard temperature (kg/m³)
JOULES_PER_KWH: float = 3.6e6  # Joules in 1 kilowatt-hour (J/kWh)
M3_PER_HA_MM: float = 10.0  # 1 mm of water depth over 1 hectare = 10 m³

# Unit scale factors
KW_PER_MW: float = 1000.0  # Kilowatts per Megawatt
KWH_PER_MWH: float = 1000.0  # Kilowatt-hours per Megawatt-hour
KWP_PER_MWP: float = 1000.0  # Kilowatt-peak per Megawatt-peak
M_PER_KM: float = 1000.0  # Meters per kilometer
HA_PER_ACRE: float = 0.404686  # Hectares per acre
ACRES_PER_HA: float = 2.47105  # Acres per hectare

# Standard aliases
RHO_WATER: float = WATER_DENSITY_KG_M3
G_ACCELERATION: float = GRAVITY_ACCELERATION_M_S2


def capital_recovery_factor(discount_rate: float, lifetime_years: float) -> float:
    """Calculate Capital Recovery Factor (CRF).

    Formula: CRF = r * (1+r)^N / ((1+r)^N - 1)
    """
    if discount_rate <= 0:
        return 1.0 / lifetime_years
    r = discount_rate
    n = lifetime_years
    return (r * ((1.0 + r) ** n)) / (((1.0 + r) ** n) - 1.0)



def depth_mm_and_area_ha_to_volume_m3(depth_mm: float, area_ha: float) -> float:
    """Calculate water volume in m³ from depth in mm and irrigated area in ha.

    Formula: V_m3 = depth_mm * 10 * area_ha (PROJECT_SPEC Module 2 Eq. 6).
    """
    if depth_mm < 0:
        raise ValueError("depth_mm cannot be negative")
    if area_ha < 0:
        raise ValueError("area_ha cannot be negative")
    return depth_mm * M3_PER_HA_MM * area_ha


def hydraulic_energy_kwh(volume_m3: float, head_m: float) -> float:
    """Calculate hydraulic energy in kWh required to lift water volume V_m3 through head H.

    Formula: E_hyd_kwh = rho * g * H * V / 3.6e6 (PROJECT_SPEC Module 2 Eq. 7).
    """
    if volume_m3 < 0:
        raise ValueError("volume_m3 cannot be negative")
    if head_m < 0:
        raise ValueError("head_m cannot be negative")
    return (WATER_DENSITY_KG_M3 * GRAVITY_ACCELERATION_M_S2 * head_m * volume_m3) / JOULES_PER_KWH


def electrical_pump_energy_kwh(
    hydraulic_energy_kwh_val: float, pump_efficiency: float, motor_efficiency: float
) -> float:
    """Calculate gross electrical energy in kWh required by the pump and motor.

    Formula: E_el_kwh = E_hyd_kwh / (eta_pump * eta_motor) (PROJECT_SPEC Module 2 Eq. 7).
    """
    if pump_efficiency <= 0.0 or pump_efficiency > 1.0:
        raise ValueError("pump_efficiency must be in (0, 1]")
    if motor_efficiency <= 0.0 or motor_efficiency > 1.0:
        raise ValueError("motor_efficiency must be in (0, 1]")
    return hydraulic_energy_kwh_val / (pump_efficiency * motor_efficiency)


def mva_to_kw(capacity_mva: float, power_factor: float) -> float:
    """Convert transformer apparent power rating (MVA) to active power limit (kW).

    Formula: P_kw = capacity_mva * 1000 * power_factor
    """
    if capacity_mva < 0:
        raise ValueError("capacity_mva cannot be negative")
    if power_factor <= 0.0 or power_factor > 1.0:
        raise ValueError("power_factor must be in (0, 1]")
    return capacity_mva * KW_PER_MW * power_factor
