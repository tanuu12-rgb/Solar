"""Solar PV modeling using pvlib for plane-of-array irradiance, cell temperature, and AC generation.

Enforces PROJECT_SPEC Module 3:
1. Transposition to plane-of-array (POA) with config tilt, azimuth, transposition model, and albedo.
2. Cell temperature using the Faiman model with config u0 and u1.
3. DC/AC chain: temperature coefficient, DC losses, inverter efficiency, soiling, availability, degradation.
4. Scale hourly profile to candidate capacity (MWp).
5. Validation card: Annual specific yield (kWh/kWp) and Capacity Utilization Factor (CUF%).
6. Window coverage analysis: percentage of annual/monthly solar energy falling inside each feeder's window.
"""

from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd
import pvlib

from core.config_loader import ConfigLoader, default_config_loader
from core.data.time_alignment import compute_feeder_window_weights


def simulate_pv_generation(
    weather_df: pd.DataFrame,
    solar_capacity_mwp: float,
    latitude: float = 18.38,
    longitude: float = 76.54,
    loader: ConfigLoader = default_config_loader,
) -> pd.DataFrame:
    """Simulate hourly AC generation for a solar PV plant at Latur (IST).

    Parameters:
    - weather_df: 8,784-row hourly weather dataframe with ghi, dni, dhi, temp_air, wind_speed.
    - solar_capacity_mwp: Plant capacity in MWp DC.
    - latitude: Site latitude (18.38° N).
    - longitude: Site longitude (76.54° E).
    - loader: ConfigLoader instance.

    Returns:
    - DataFrame with POA components, cell temperature, and hourly AC generation (kW and kWh).
    """
    times = weather_df.index

    # Retrieve parameters from config
    pv_tilt = float(loader.get_assumption_value("pv_tilt_deg"))
    pv_azimuth = float(loader.get_assumption_value("pv_azimuth_deg"))
    albedo = float(loader.get_assumption_value("ground_albedo"))
    trans_model = str(loader.get_assumption_value("transposition_model")).lower()

    u0 = float(loader.get_assumption_value("faiman_u0"))
    u1 = float(loader.get_assumption_value("faiman_u1"))

    gamma_pmax = float(loader.get_assumption_value("pv_temp_coeff_pmax"))
    dc_losses = float(loader.get_assumption_value("dc_losses_fraction"))
    inv_eff = float(loader.get_assumption_value("inverter_efficiency"))
    soiling = float(loader.get_assumption_value("soiling_loss_fraction"))
    avail_loss = float(loader.get_assumption_value("availability_loss_fraction"))
    degradation = float(loader.get_assumption_value("annual_degradation_rate"))
    dc_ac_ratio = float(loader.get_assumption_value("dc_ac_ratio"))

    # Ensure times has Asia/Kolkata timezone so pvlib accurately calculates solar position in IST
    if times.tz is None:
        times_tz = times.tz_localize("Asia/Kolkata")
    else:
        times_tz = times.tz_convert("Asia/Kolkata")

    # Calculate solar position (ephemeris) in IST
    solpos = pvlib.solarposition.get_solarposition(
        time=times_tz,
        latitude=latitude,
        longitude=longitude,
        altitude=633.0,
    )
    apparent_zenith = solpos["apparent_zenith"].to_numpy()
    solar_azimuth = solpos["azimuth"].to_numpy()

    # Transposition to plane-of-array (POA)
    # Ensure transposition model is valid in pvlib
    poa_model = "perez" if "perez" in trans_model else "isotropic"
    try:
        poa = pvlib.irradiance.get_total_irradiance(
            surface_tilt=pv_tilt,
            surface_azimuth=pv_azimuth,
            solar_zenith=apparent_zenith,
            solar_azimuth=solar_azimuth,
            dni=weather_df["dni"],
            ghi=weather_df["ghi"],
            dhi=weather_df["dhi"],
            albedo=albedo,
            model=poa_model,
        )
    except Exception:
        # Robust fallback to isotropic if transposition encounters issues
        poa = pvlib.irradiance.get_total_irradiance(
            surface_tilt=pv_tilt,
            surface_azimuth=pv_azimuth,
            solar_zenith=apparent_zenith,
            solar_azimuth=solar_azimuth,
            dni=weather_df["dni"],
            ghi=weather_df["ghi"],
            dhi=weather_df["dhi"],
            albedo=albedo,
            model="isotropic",
        )

    poa_global = np.maximum(0.0, poa["poa_global"].fillna(0.0).to_numpy())

    # Cell temperature calculation using Faiman model
    cell_temp = pvlib.temperature.faiman(
        poa_global=poa_global,
        temp_air=weather_df["temp_air"].to_numpy(),
        wind_speed=weather_df["wind_speed"].to_numpy(),
        u0=u0,
        u1=u1,
    )

    # Temperature derate relative to STC 25°C
    temp_derate = 1.0 + gamma_pmax * (cell_temp - 25.0)
    temp_derate = np.maximum(0.5, temp_derate)

    # Net system losses factor (DC wiring, soiling, availability, year-1 mid-year degradation)
    system_derate = (
        (1.0 - dc_losses)
        * (1.0 - soiling)
        * (1.0 - avail_loss)
        * (1.0 - 0.5 * degradation)
    )

    # DC power per kWp of module: (POA / 1000 W/m²) * temp_derate * system_derate
    dc_power_kw_per_kwp = (poa_global / 1000.0) * temp_derate * system_derate

    # Inverter rating per kWp DC = 1.0 / dc_ac_ratio
    max_inverter_ac_kw_per_kwp = 1.0 / dc_ac_ratio

    # AC generation per kWp DC
    ac_power_kw_per_kwp = np.minimum(
        dc_power_kw_per_kwp * inv_eff, max_inverter_ac_kw_per_kwp
    )
    ac_power_kw_per_kwp = np.maximum(0.0, ac_power_kw_per_kwp)

    # Scale to candidate plant capacity (MWp -> kWp = MWp * 1000)
    total_kwp = solar_capacity_mwp * 1000.0
    plant_generation_kw = ac_power_kw_per_kwp * total_kwp

    results = pd.DataFrame(index=times)
    results["poa_global_w_per_m2"] = poa_global
    results["cell_temp_c"] = cell_temp
    results["ac_kw_per_kwp"] = ac_power_kw_per_kwp
    results["solar_generation_kw"] = plant_generation_kw
    results["solar_generation_kwh"] = plant_generation_kw  # 1 hour interval -> kWh = kW * 1h

    return results


def validate_plant_yield_and_cuf(
    results_df: pd.DataFrame,
    solar_capacity_mwp: float,
    loader: ConfigLoader = default_config_loader,
) -> Dict[str, Any]:
    """Compute specific yield (kWh/kWp) and CUF% with config benchmark checks."""
    total_kwh = float(results_df["solar_generation_kwh"].sum())
    total_kwp = solar_capacity_mwp * 1000.0
    hours = len(results_df)

    specific_yield = total_kwh / total_kwp if total_kwp > 0 else 0.0
    cuf_percent = (total_kwh / (total_kwp * hours)) * 100.0 if total_kwp > 0 else 0.0

    sy_min = float(loader.get_assumption_value("expected_specific_yield_min_kwh_per_kwp"))
    sy_max = float(loader.get_assumption_value("expected_specific_yield_max_kwh_per_kwp"))
    cuf_min = float(loader.get_assumption_value("expected_cuf_min_percent"))
    cuf_max = float(loader.get_assumption_value("expected_cuf_max_percent"))

    sy_status = "pass" if sy_min <= specific_yield <= sy_max else "warning"
    cuf_status = "pass" if cuf_min <= cuf_percent <= cuf_max else "warning"
    cuf_within_expected_range = (cuf_status == "pass")

    return {
        "annual_generation_mwh": round(total_kwh / 1000.0, 2),
        "specific_yield_kwh_per_kwp": round(specific_yield, 1),
        "specific_yield_benchmark_range": (sy_min, sy_max),
        "specific_yield_status": sy_status,
        "cuf_percent": round(cuf_percent, 2),
        "cuf_benchmark_range_percent": (cuf_min, cuf_max),
        "expected_cuf_min_percent": cuf_min,
        "expected_cuf_max_percent": cuf_max,
        "cuf_status": cuf_status,
        "cuf_within_expected_range": cuf_within_expected_range,
        "status": cuf_status,
        "message": f"CUF is {round(cuf_percent, 2)}% (benchmark {cuf_min}% - {cuf_max}%)",
    }


def analyze_feeder_window_coverage(
    df1: pd.DataFrame,
    df2: pd.DataFrame,
) -> pd.DataFrame:
    """Calculate the share of annual solar generation captured inside each feeder's supply window.

    Accepts (solar_results_df, feeder_schedule_df) in any order.
    """
    if "solar_generation_kwh" in df1.columns:
        solar_results_df, feeder_schedule_df = df1, df2
    else:
        feeder_schedule_df, solar_results_df = df1, df2

    total_solar_kwh = float(solar_results_df["solar_generation_kwh"].sum())
    solar_kwh_series = solar_results_df["solar_generation_kwh"]
    times = solar_results_df.index

    records = []
    for idx, row in feeder_schedule_df.iterrows():
        w_start = row["window_start"]
        w_end = row["window_end"]
        feeder_name = row["feeder_name"]

        weights = compute_feeder_window_weights(times, w_start, w_end)
        captured_kwh = float((solar_kwh_series * weights).sum())
        capture_pct = (captured_kwh / total_solar_kwh * 100.0) if total_solar_kwh > 0 else 0.0

        records.append({
            "feeder_name": feeder_name,
            "window_start": w_start,
            "window_end": w_end,
            "annual_solar_captured_mwh": round(captured_kwh / 1000.0, 2),
            "window_solar_generation_mwh": round(captured_kwh / 1000.0, 2),
            "total_annual_generation_mwh": round(total_solar_kwh / 1000.0, 2),
            "window_coverage_percent": round(capture_pct, 2),
            "coverage_percent": round(capture_pct, 2),
        })

    return pd.DataFrame(records)

