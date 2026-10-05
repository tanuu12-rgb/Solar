"""Time alignment and supply window overlap weighting for 2024 hourly profiles.

Under approved change (1), weather data is already unified in IST.
This module provides fractional-hour overlap weights for staggered agricultural
supply windows with quarter-hour offsets (e.g. 07:30-15:30, 09:15-17:15, 10:00-18:00).
"""

import numpy as np
import pandas as pd

from core.errors import DataValidationError


def parse_time_to_minutes(t_str: str) -> int:
    """Convert 'HH:MM' string to minutes from midnight."""
    parts = [int(p.strip()) for p in t_str.split(":")]
    return parts[0] * 60 + parts[1]


def compute_hourly_window_weight(
    hour_start_min: int, hour_end_min: int, win_start_min: int, win_end_min: int
) -> float:
    """Calculate the fractional overlap of [hour_start_min, hour_end_min] with [win_start_min, win_end_min]."""
    overlap_start = max(hour_start_min, win_start_min)
    overlap_end = min(hour_end_min, win_end_min)
    if overlap_end > overlap_start:
        return (overlap_end - overlap_start) / 60.0
    return 0.0


def compute_feeder_window_weights(
    times: pd.DatetimeIndex, window_start: str, window_end: str
) -> np.ndarray:
    """Compute fractional-hour overlap weights for each timestamp in times.

    For example:
    - If window is 09:15 to 17:15:
      - 09:00 - 10:00 has 45 minutes overlap -> weight = 0.75
      - 10:00 - 17:00 (7 hours) -> weight = 1.0 each
      - 17:00 - 18:00 has 15 minutes overlap -> weight = 0.25
      - Total day weight sum = 0.75 + 7.0 + 0.25 = 8.0 hours.
    """
    win_start_min = parse_time_to_minutes(window_start)
    win_end_min = parse_time_to_minutes(window_end)
    duration_hours = (win_end_min - win_start_min) / 60.0
    if abs(duration_hours - 8.0) > 1e-4:
        raise DataValidationError(
            f"Supply window {window_start} to {window_end} duration is {duration_hours} h, expected 8.0 h"
        )

    # Compute 24-hour daily weights template
    daily_weights = np.zeros(24, dtype=float)
    for h in range(24):
        h_start = h * 60
        h_end = (h + 1) * 60
        daily_weights[h] = compute_hourly_window_weight(
            h_start, h_end, win_start_min, win_end_min
        )

    # Verify 24-hour sum equals exactly 8.0
    assert abs(np.sum(daily_weights) - 8.0) < 1e-6, f"Daily window weight sum is {np.sum(daily_weights)}, expected 8.0"

    # Map by hour of timestamp
    hours = times.hour.to_numpy()
    weights = daily_weights[hours]
    return pd.Series(weights, index=times)


# Backward-compatible alias
compute_supply_window_overlap_weights = compute_feeder_window_weights

