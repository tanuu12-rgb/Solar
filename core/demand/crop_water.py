"""Crop water requirements and evapotranspiration calculations (FAO-56).

Enforces PROJECT_SPEC Module 2:
1. Daily ET0 from Open-Meteo.
2. Daily Kc(t) linear interpolation from stage lengths and planting dates in crop_params.csv.
3. Daily ETc = Kc(t) * ET0.
4. Effective rainfall (FAO-56 dependable rain or USDA SCS).
5. Net irrigation requirement: NIR_mm = max(0, ETc - Peff).
6. Gross irrigation requirement: GIR_mm = NIR_mm / irrigation_efficiency.
7. Water volume: V_m3 = GIR_mm * 10 * area_ha.
"""

from typing import Dict, List, Optional
import numpy as np
import pandas as pd

from core.config_loader import ConfigLoader, default_config_loader
from core.data.loaders import load_crop_parameters


def calculate_fao56_kc_curve(
    day_of_year_series: pd.Series,
    planting_date_str: str,
    l_ini: int,
    l_dev: int,
    l_mid: int,
    l_end: int,
    kc_ini: float,
    kc_mid: float,
    kc_end: float,
    year: int = 2024,
) -> np.ndarray:
    """Calculate daily FAO-56 crop coefficient Kc array over the year."""
    # Planting day of year
    parts = [int(p) for p in planting_date_str.split("-")]
    plant_dt = pd.Timestamp(year=year, month=parts[0], day=parts[1])
    plant_doy = plant_dt.dayofyear

    total_season = l_ini + l_dev + l_mid + l_end
    doy = day_of_year_series.to_numpy()

    kc_array = np.zeros(len(doy), dtype=float)

    days_in_year = 366 if pd.Timestamp(year=year, month=12, day=31).dayofyear == 366 else 365
    crosses_year = (plant_doy + total_season) > days_in_year

    for i, d in enumerate(doy):
        # Handle crop cycles that wrap across calendar year boundary (e.g. Rabi crops)
        if crosses_year:
            if d >= plant_doy:
                growth_day = d - plant_doy
            elif d < (plant_doy + total_season - days_in_year):
                growth_day = d + days_in_year - plant_doy
            else:
                growth_day = -1
        else:
            growth_day = d - plant_doy

        if 0 <= growth_day < total_season:
            if growth_day < l_ini:
                kc = kc_ini
            elif growth_day < l_ini + l_dev:
                frac = (growth_day - l_ini) / float(l_dev)
                kc = kc_ini + frac * (kc_mid - kc_ini)
            elif growth_day < l_ini + l_dev + l_mid:
                kc = kc_mid
            else:
                frac = (growth_day - (l_ini + l_dev + l_mid)) / float(l_end)
                kc = kc_mid + frac * (kc_end - kc_mid)
            kc_array[i] = max(0.0, kc)
        else:
            kc_array[i] = 0.0

    return kc_array


def calculate_fao56_daily_kc(
    dates: pd.DatetimeIndex,
    planting_date_str: str,
    l_ini: int,
    l_dev: int,
    l_mid: int,
    l_end: int,
    kc_ini: float,
    kc_mid: float,
    kc_end: float,
    year: int = 2024,
) -> pd.Series:
    """Calculate daily FAO-56 crop coefficient Kc Series over given DatetimeIndex."""
    doy_series = pd.Series(dates.dayofyear, index=dates)
    arr = calculate_fao56_kc_curve(
        doy_series,
        planting_date_str=planting_date_str,
        l_ini=l_ini,
        l_dev=l_dev,
        l_mid=l_mid,
        l_end=l_end,
        kc_ini=kc_ini,
        kc_mid=kc_mid,
        kc_end=kc_end,
        year=year,
    )
    return pd.Series(arr, index=dates)


def calculate_effective_rainfall_usda(p_mm: float) -> float:
    """USDA SCS effective rainfall calculation for a single daily amount."""
    if p_mm <= 0.0:
        return 0.0
    if p_mm <= 250.0:
        return float(p_mm * (125.0 - 0.2 * p_mm) / 125.0)
    return float(125.0 + 0.1 * p_mm)


def calculate_effective_rainfall(
    precip_mm: pd.Series,
    method: str = "fao_56_dependable",
) -> pd.Series:
    """Calculate effective rainfall from daily precipitation series.

    Methods:
    - fao_56_dependable: FAO dependable rainfall empirical formula.
    - usda_scs: USDA Soil Conservation Service formula.
    """
    p = precip_mm.copy()
    if method == "fao_56_dependable":
        # Daily formula adapted from FAO dependable rainfall
        # Peff = 0.8 * P - 0.8 mm if P > 1.0 mm else 0
        peff = np.where(p > 1.0, np.maximum(0.0, 0.75 * p - 0.5), 0.0)
    elif method == "usda_scs":
        # USDA SCS daily empirical relation
        peff = np.where(p > 0.0, p * np.maximum(0.0, (125.0 - 0.2 * p) / 125.0), 0.0)
    else:
        peff = np.maximum(0.0, 0.70 * p)

    return pd.Series(peff, index=precip_mm.index, name="peff_mm")


def calculate_daily_crop_water_requirements(
    weather_df: pd.DataFrame,
    crop_mix: Optional[Dict[str, float]] = None,
    crop_mix_ha: Optional[Dict[str, float]] = None,
    irrigation_methods: Optional[Dict[str, str]] = None,
    crop_params_df: Optional[pd.DataFrame] = None,
    loader: ConfigLoader = default_config_loader,
) -> pd.DataFrame:
    """Compute daily crop evapotranspiration, NIR, GIR, and water volume for the crop mix.

    Parameters:
    - weather_df: 8784-row hourly weather dataframe with et0_mm, precip_mm.
    - crop_mix / crop_mix_ha: Dictionary mapping crop name to area in hectares.
    - irrigation_methods: Dictionary mapping crop name to 'drip', 'sprinkler', or 'surface'.
    - crop_params_df: DataFrame loaded from crop_params.csv.
    - loader: ConfigLoader instance.
    """
    target_crop_mix = crop_mix if crop_mix is not None else (crop_mix_ha or {})
    crop_mix = target_crop_mix
    if crop_params_df is None:
        crop_params_df = load_crop_parameters()

    irrigation_methods = irrigation_methods or {}
    eff_drip = float(loader.get_assumption_value("irrigation_efficiency_drip"))
    eff_sprinkler = float(loader.get_assumption_value("irrigation_efficiency_sprinkler"))
    eff_surface = float(loader.get_assumption_value("irrigation_efficiency_surface"))
    eff_map = {
        "drip": eff_drip,
        "sprinkler": eff_sprinkler,
        "surface": eff_surface,
    }

    rainfall_method = str(loader.get_assumption_value("effective_rainfall_method"))

    # Aggregate hourly weather to daily
    daily_weather = weather_df.resample("D").agg({
        "et0_mm": "sum",
        "precip_mm": "sum",
        "temp_air": "mean",
    })

    daily_peff = calculate_effective_rainfall(daily_weather["precip_mm"], method=rainfall_method)

    daily_results = pd.DataFrame(index=daily_weather.index)
    daily_results["et0_mm"] = daily_weather["et0_mm"]
    daily_results["precip_mm"] = daily_weather["precip_mm"]
    daily_results["peff_mm"] = daily_peff

    total_volume_m3 = np.zeros(len(daily_weather), dtype=float)
    total_area_ha = sum(crop_mix.values())

    doy_series = pd.Series(daily_weather.index.dayofyear, index=daily_weather.index)

    for crop, area_ha in crop_mix.items():
        if area_ha <= 0:
            continue
        if crop not in crop_params_df.index:
            # Fallback to nearest crop or first crop
            c_row = crop_params_df.iloc[0]
        else:
            c_row = crop_params_df.loc[crop]

        kc_curve = calculate_fao56_kc_curve(
            day_of_year_series=doy_series,
            planting_date_str=str(c_row["planting_date"]),
            l_ini=int(c_row["l_ini"]),
            l_dev=int(c_row["l_dev"]),
            l_mid=int(c_row["l_mid"]),
            l_end=int(c_row["l_end"]),
            kc_ini=float(c_row["kc_ini"]),
            kc_mid=float(c_row["kc_mid"]),
            kc_end=float(c_row["kc_end"]),
            year=2024,
        )

        daily_results[f"kc_{crop}"] = kc_curve
        etc_mm = kc_curve * daily_weather["et0_mm"].to_numpy()
        daily_results[f"etc_mm_{crop}"] = etc_mm

        # NIR = max(0, ETc - Peff)
        nir_mm = np.maximum(0.0, etc_mm - daily_peff.to_numpy())
        daily_results[f"nir_mm_{crop}"] = nir_mm

        # Efficiency
        method = irrigation_methods.get(crop, "drip" if crop in ["Sugarcane", "Tomato"] else "surface")
        eff = eff_map.get(method.lower(), eff_surface)
        gir_mm = nir_mm / eff
        daily_results[f"gir_mm_{crop}"] = gir_mm

        # Volume V_m3 = GIR_mm * 10 * area_ha
        v_m3 = gir_mm * 10.0 * area_ha
        daily_results[f"vol_m3_{crop}"] = v_m3
        total_volume_m3 += v_m3

    daily_results["total_water_volume_m3"] = total_volume_m3
    daily_results["total_area_ha"] = total_area_ha

    return daily_results
