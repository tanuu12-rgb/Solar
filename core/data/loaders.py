"""Data loaders for Open-Meteo weather dataset, Feeder Schedule, and FAO-56 Crop Parameters.

Per approved design:
1. Single Open-Meteo CSV containing temperature, wind, ET0, precipitation, shortwave_radiation,
   DNI and DHI in IST.
2. Irrigation crop mix taken as user input with crop parameter references from crop_params.csv.
3. Feeder schedule filtered for the target substation.
"""

import logging
from pathlib import Path
from typing import Optional
import pandas as pd

from core.config_loader import get_project_root
from core.errors import MissingInputError, DataValidationError

logger = logging.getLogger(__name__)


def get_default_data_dir() -> Path:
    """Return default path to data/raw directory."""
    return get_project_root() / "data" / "raw"


def load_weather_data(path: Optional[Path] = None) -> pd.DataFrame:
    """Load and parse the single 2024 Open-Meteo hourly weather dataset for Latur (IST).

    Returns a clean DataFrame with 8,784 rows and standardized columns:
    - time (pd.DatetimeIndex in IST)
    - temp_air (°C)
    - wind_speed (m/s, converted from km/h)
    - ghi (W/m², shortwave solar irradiance)
    - dni (W/m², direct normal irradiance)
    - dhi (W/m², diffuse horizontal irradiance)
    - precip_mm (mm/h)
    - et0_mm (mm/h)
    - rh (%)
    """
    file_path = path or (get_default_data_dir() / "open-meteo-18.38N76.54E633m.csv")
    if not file_path.exists():
        raise MissingInputError(
            "open_meteo_csv",
            f"Open-Meteo weather file not found at {file_path}",
        )

    # Header has metadata on lines 1-2, blank on line 3, CSV header on line 4
    try:
        df = pd.read_csv(file_path, skiprows=3, encoding="utf-8")
    except Exception as e:
        raise DataValidationError(f"Failed to read weather CSV at {file_path}: {e}") from e

    expected_cols = {
        "time",
        "temperature_2m (°C)",
        "precipitation (mm)",
        "et0_fao_evapotranspiration (mm)",
        "relative_humidity_2m (%)",
        "wind_speed_10m (km/h)",
        "shortwave_radiation (W/m²)",
        "direct_normal_irradiance (W/m²)",
        "diffuse_radiation (W/m²)",
    }
    missing_cols = expected_cols - set(df.columns)
    if missing_cols:
        raise DataValidationError(
            f"Weather CSV is missing required columns: {sorted(missing_cols)}"
        )

    if len(df) != 8784:
        raise DataValidationError(
            f"Weather dataset must have exactly 8,784 hourly rows for 2024, found {len(df)}"
        )

    if df.isna().any().any():
        null_counts = df.isna().sum().to_dict()
        raise DataValidationError(f"Weather dataset contains null values: {null_counts}")

    # Parse timestamps as IST
    df["time"] = pd.to_datetime(df["time"])
    df = df.set_index("time")

    # Rename to clean standard variables
    clean_df = pd.DataFrame(index=df.index)
    clean_df["temp_air"] = df["temperature_2m (°C)"].astype(float)
    clean_df["precip_mm"] = df["precipitation (mm)"].astype(float)
    clean_df["et0_mm"] = df["et0_fao_evapotranspiration (mm)"].astype(float)
    clean_df["rh"] = df["relative_humidity_2m (%)"].astype(float)
    # Convert wind speed from km/h to m/s
    clean_df["wind_speed"] = (df["wind_speed_10m (km/h)"].astype(float) / 3.6).round(4)
    clean_df["ghi"] = df["shortwave_radiation (W/m²)"].astype(float)
    clean_df["dni"] = df["direct_normal_irradiance (W/m²)"].astype(float)
    clean_df["dhi"] = df["diffuse_radiation (W/m²)"].astype(float)

    # Aliases for original names
    clean_df["temperature_2m"] = clean_df["temp_air"]
    clean_df["precipitation"] = clean_df["precip_mm"]
    clean_df["et0_fao_evapotranspiration"] = clean_df["et0_mm"]
    clean_df["relative_humidity_2m"] = clean_df["rh"]
    clean_df["wind_speed_10m"] = (clean_df["wind_speed"] * 3.6).round(2)
    clean_df["shortwave_radiation"] = clean_df["ghi"]
    clean_df["direct_normal_irradiance"] = clean_df["dni"]
    clean_df["diffuse_radiation"] = clean_df["dhi"]

    logger.info(
        "Loaded Open-Meteo weather dataset: %d rows from %s to %s",
        len(clean_df),
        clean_df.index[0],
        clean_df.index[-1],
    )
    return clean_df


def load_feeder_schedule(
    path: Optional[Path] = None, substation_filter: Optional[str] = None
) -> pd.DataFrame:
    """Load feeder schedule transcribed from MSEDCL KUSUM-C Annexure-A letter.

    Validates that each window equals exactly 8 hours.
    """
    file_path = path or (get_default_data_dir() / "feeder_schedule.csv")
    if not file_path.exists():
        raise MissingInputError(
            "feeder_schedule.csv",
            f"Feeder schedule file not found at {file_path}",
        )

    try:
        df = pd.read_csv(file_path, encoding="utf-8")
    except Exception as e:
        raise DataValidationError(f"Failed to read feeder schedule at {file_path}: {e}") from e

    req_cols = [
        "district",
        "taluka",
        "substation",
        "pt_capacity_mva",
        "solar_plant_mw",
        "feeder_name",
        "feeder_type",
        "window_start",
        "window_end",
    ]
    for col in req_cols:
        if col not in df.columns:
            raise DataValidationError(f"feeder_schedule.csv missing required column: '{col}'")

    if df.empty:
        raise DataValidationError("feeder_schedule.csv is empty")

    if substation_filter:
        df = df[df["substation"].str.strip().str.lower() == substation_filter.strip().lower()].copy()
        if df.empty:
            raise DataValidationError(
                f"Substation '{substation_filter}' not found in feeder schedule"
            )

    # Validate 8 hour window duration for each row
    for idx, row in df.iterrows():
        start_parts = [int(p) for p in str(row["window_start"]).split(":")]
        end_parts = [int(p) for p in str(row["window_end"]).split(":")]
        start_min = start_parts[0] * 60 + start_parts[1]
        end_min = end_parts[0] * 60 + end_parts[1]
        duration_hours = (end_min - start_min) / 60.0
        if abs(duration_hours - 8.0) > 1e-4:
            raise DataValidationError(
                f"Feeder '{row['feeder_name']}' window duration is {duration_hours} h, expected 8.0 h"
            )

    return df


def load_crop_parameters(path: Optional[Path] = None) -> pd.DataFrame:
    """Load FAO-56 crop growth stage lengths and crop coefficients."""
    file_path = path or (get_default_data_dir() / "crop_params.csv")
    if not file_path.exists():
        raise MissingInputError(
            "crop_params.csv",
            f"FAO-56 Crop parameters file not found at {file_path}",
        )

    try:
        df = pd.read_csv(file_path, encoding="utf-8")
    except Exception as e:
        raise DataValidationError(f"Failed to read crop params at {file_path}: {e}") from e

    req_cols = ["crop", "planting_date", "l_ini", "l_dev", "l_mid", "l_end", "kc_ini", "kc_mid", "kc_end"]
    for col in req_cols:
        if col not in df.columns:
            raise DataValidationError(f"crop_params.csv missing required column: '{col}'")

    df = df.set_index("crop", drop=False)
    return df


def load_district_proxy_crop_shares(
    path: Optional[Path] = None,
) -> pd.Series:
    """Derive district-level irrigated crop-mix percentage shares from 2011-12 Latur data.

    Tagged SOURCED (district level, 2011-12, proxy for feeder, not measured feeder data).
    Handles Ahmadpur (TALUKA_ID 4228) duplicate row explicitly.
    Returns Series with crop names and fraction shares summing to 1.0.
    """
    import zipfile
    import xml.etree.ElementTree as ET

    extracted_path = get_project_root() / "data" / "raw" / "extracted" / "2011-12_Irrigation_Area_Latur.xml"
    zip_path = path or (get_default_data_dir() / "2011-12_Irrigation_Area_Latur.zip")

    if extracted_path.exists():
        tree = ET.parse(extracted_path)
        root = tree.getroot()
    elif zip_path.exists():
        with zipfile.ZipFile(zip_path, "r") as zf:
            content = zf.read("2011-12_Irrigation_Area_Latur.xml")
        root = ET.fromstring(content)
    else:
        raise MissingInputError(
            "2011-12_Irrigation_Area_Latur",
            f"Neither extracted XML ({extracted_path}) nor ZIP ({zip_path}) found",
        )

    records = [{sub.tag: (sub.text.strip() if sub.text else "") for sub in child} for child in root]
    df = pd.DataFrame(records)

    # Deduplicate Ahmadpur (TALUKA_ID 4228)
    if "TALUKA_ID" in df.columns:
        df = df.drop_duplicates(subset=["TALUKA_ID"]).copy()

    crops_map = {
        "Soybean": "SOYABEAN_AR_UNDER_IRR",
        "Gram": "GRAM_AR_UNDER_IRR",
        "Sugarcane": "SUGARCANE_AR_UNDER_IRR",
        "Tur": "TUR_AR_UNDER_IRR",
        "Wheat": "WHEAT_AR_UNDER_IRR",
    }

    totals = {}
    for crop, col in crops_map.items():
        if col in df.columns:
            series = pd.to_numeric(df[col].replace(".", None), errors="coerce").fillna(0.0)
            totals[crop] = float(series.sum())
        else:
            totals[crop] = 0.0

    total_sum = sum(totals.values())
    if total_sum <= 0:
        raise DataValidationError("Total irrigated area across 5 proxy crops is zero or invalid")

    shares = {crop: round(totals[crop] / total_sum, 4) for crop in totals}
    return pd.Series(shares, name="district_proxy_share")


def calculate_district_proxy_crop_mix(
    command_area_ha: float,
    path: Optional[Path] = None,
) -> dict[str, float]:
    """Calculate feeder crop hectares by scaling district-level shares to user-entered command area."""
    if command_area_ha <= 0:
        raise ValueError("Total command area must be positive")
    shares = load_district_proxy_crop_shares(path)
    return {crop: round(float(share * command_area_ha), 1) for crop, share in shares.items()}


