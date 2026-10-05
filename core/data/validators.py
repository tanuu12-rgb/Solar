"""Data validation and sanity checks for weather and operational parameters.

Per PROJECT_SPEC Section 3 and Section 8.
"""

from typing import Any, Dict
import pandas as pd

from core.config_loader import ConfigLoader, default_config_loader
from core.errors import DataValidationError


def validate_weather_dataset(
    df: pd.DataFrame, loader: ConfigLoader = default_config_loader
) -> Dict[str, Any]:
    """Execute domain sanity checks on the 2024 hourly weather dataset.

    Checks:
    1. Exact 8,784 hourly rows.
    2. No null or NaN values.
    3. Annual rainfall (mm) against IMD normal reference range.
    4. Annual GHI (kWh/m²) against SECI/NISE regional sanity range.
    5. Annual ET₀ (mm) against regional FAO-56 range.
    """
    if len(df) != 8784:
        raise DataValidationError(f"Expected 8,784 hourly rows, got {len(df)}")

    if df.isna().any().any():
        raise DataValidationError("Weather dataset contains unexpected missing values")

    ghi_col = "ghi" if "ghi" in df.columns else "shortwave_radiation"
    precip_col = "precip_mm" if "precip_mm" in df.columns else "precipitation"
    et0_col = "et0_mm" if "et0_mm" in df.columns else "et0_fao_evapotranspiration"

    for col in ["ghi", "shortwave_radiation", "direct_normal_irradiance", "diffuse_radiation", "dni", "dhi"]:
        if col in df.columns and (df[col] < 0.0).any():
            bad_times = [str(t) for t in df.index[df[col] < 0.0]]
            raise DataValidationError(f"Physically impossible negative solar irradiance detected in column '{col}'", timestamps=bad_times)

    if (df[precip_col] < 0.0).any():
        bad_times = [str(t) for t in df.index[df[precip_col] < 0.0]]
        raise DataValidationError("Negative precipitation detected in weather dataset", timestamps=bad_times)


    annual_rainfall_mm = float(df[precip_col].sum())
    # GHI is W/m² hourly -> Wh/m² per hour, sum/1000 = kWh/m²
    annual_ghi_kwh_per_m2 = float(df[ghi_col].sum() / 1000.0)
    annual_et0_mm = float(df[et0_col].sum())


    rf_min = float(loader.get_assumption_value("latur_annual_rainfall_reference_min_mm"))
    rf_max = float(loader.get_assumption_value("latur_annual_rainfall_reference_max_mm"))
    ghi_min = float(loader.get_assumption_value("expected_annual_ghi_min_kwh_per_m2"))
    ghi_max = float(loader.get_assumption_value("expected_annual_ghi_max_kwh_per_m2"))
    et0_min = float(loader.get_assumption_value("expected_annual_et0_min_mm"))
    et0_max = float(loader.get_assumption_value("expected_annual_et0_max_mm"))

    rainfall_status = "normal" if rf_min <= annual_rainfall_mm <= rf_max else "flagged"
    ghi_status = "normal" if ghi_min <= annual_ghi_kwh_per_m2 <= ghi_max else "flagged"
    et0_status = "normal" if et0_min <= annual_et0_mm <= et0_max else "flagged"

    report = {
        "rows": len(df),
        "start_time": str(df.index[0]),
        "end_time": str(df.index[-1]),
        "annual_rainfall_mm": round(annual_rainfall_mm, 1),
        "rainfall_ref_range_mm": (rf_min, rf_max),
        "rainfall_status": rainfall_status,
        "annual_ghi_kwh_per_m2": round(annual_ghi_kwh_per_m2, 1),
        "ghi_ref_range_kwh_per_m2": (ghi_min, ghi_max),
        "ghi_status": ghi_status,
        "annual_et0_mm": round(annual_et0_mm, 1),
        "et0_ref_range_mm": (et0_min, et0_max),
        "et0_status": et0_status,
        "max_temperature_c": round(float(df["temp_air"].max()), 1),
        "min_temperature_c": round(float(df["temp_air"].min()), 1),
        "mean_wind_speed_ms": round(float(df["wind_speed"].mean()), 2),
    }

    return report
