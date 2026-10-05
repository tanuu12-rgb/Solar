"""Hourly irrigation electrical demand profile across feeder supply windows.

Enforces PROJECT_SPEC Module 2 Item 8:
Distribute daily electrical energy over the feeder's real supply window (fractional-hour weights).
If daily requirement exceeds what the window can deliver at connected pump capacity,
report as unmet demand; never scale silently.
"""

from typing import Dict, Any, Optional
import numpy as np
import pandas as pd

from core.data.time_alignment import compute_feeder_window_weights


def build_hourly_irrigation_demand_profile(
    daily_results_df: Optional[pd.DataFrame] = None,
    hourly_index: Optional[pd.DatetimeIndex] = None,
    window_start: str = "10:00",
    window_end: str = "18:00",
    connected_pump_capacity_kw: float = 1000.0,
    daily_demand_df: Optional[pd.DataFrame] = None,
    hourly_timestamps: Optional[pd.DatetimeIndex] = None,
) -> pd.DataFrame:
    """Disaggregate daily electrical energy into an 8,784-row hourly irrigation demand profile."""
    df_in = daily_results_df if daily_results_df is not None else daily_demand_df
    idx_in = hourly_index if hourly_index is not None else hourly_timestamps
    if df_in is None or idx_in is None:
        raise ValueError("Must supply daily demand dataframe and hourly index")

    weights = compute_feeder_window_weights(idx_in, window_start, window_end)

    # Reindex daily e_el_kwh to hourly index by mapping dates
    daily_e_el = df_in["e_el_kwh"]
    daily_map = daily_e_el.to_dict()

    dates = idx_in.normalize()
    hourly_daily_total = np.array([daily_map.get(d, 0.0) for d in dates])

    # In each 8-hour window, the base delivery rate is daily_total / 8.0 kW
    # Multiplied by the fractional hourly weight (which sums to 8.0 per day)
    base_kw = hourly_daily_total / 8.0
    demanded_kw = base_kw * weights

    # Compare with connected pump capacity
    # If demanded_kw > connected_pump_capacity_kw, the pump cannot deliver the required flow rate in 8h
    actual_kw = np.minimum(demanded_kw, connected_pump_capacity_kw)
    unmet_kw = np.maximum(0.0, demanded_kw - connected_pump_capacity_kw)

    profile_df = pd.DataFrame(index=hourly_index)
    profile_df["window_weight"] = weights
    profile_df["pump_demanded_kw"] = demanded_kw
    profile_df["pump_served_kw"] = actual_kw
    profile_df["pump_unmet_kw"] = unmet_kw
    profile_df["connected_pump_capacity_kw"] = connected_pump_capacity_kw

    # Hourly energy (kWh) equals kW * 1h
    profile_df["pump_demand_kwh"] = demanded_kw
    profile_df["pump_served_kwh"] = actual_kw
    profile_df["pump_unmet_kwh"] = unmet_kw

    return profile_df


def summarize_irrigation_demand(profile_df: pd.DataFrame) -> Dict[str, Any]:
    """Calculate summary KPIs for annual irrigation demand."""
    total_demand_mwh = float(profile_df["pump_demand_kwh"].sum() / 1000.0)
    total_served_mwh = float(profile_df["pump_served_kwh"].sum() / 1000.0)
    total_unmet_mwh = float(profile_df["pump_unmet_kwh"].sum() / 1000.0)
    peak_demand_kw = float(profile_df["pump_demanded_kw"].max())

    unmet_fraction = total_unmet_mwh / total_demand_mwh if total_demand_mwh > 0 else 0.0

    return {
        "annual_demand_mwh": round(total_demand_mwh, 2),
        "annual_served_mwh": round(total_served_mwh, 2),
        "annual_unmet_mwh": round(total_unmet_mwh, 2),
        "unmet_percentage": round(unmet_fraction * 100.0, 2),
        "peak_demand_kw": round(peak_demand_kw, 2),
    }
