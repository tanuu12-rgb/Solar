"""Unit tests for time alignment and supply window overlap weighting."""

import pandas as pd
import numpy as np
from core.data.time_alignment import compute_supply_window_overlap_weights


def test_window_overlap_weights_integer_hours() -> None:
    """Verify an integer 8h window (10:00 to 18:00) gives weight 1.0 for 8 hours and 0 elsewhere."""
    dates = pd.date_range("2024-01-01 00:00:00", "2024-01-01 23:00:00", freq="1h")
    weights = compute_supply_window_overlap_weights(dates, "10:00", "18:00")

    assert weights.sum() == 8.0
    for i, dt in enumerate(dates):
        if 10 <= dt.hour < 18:
            assert weights.iloc[i] == 1.0
        else:
            assert weights.iloc[i] == 0.0


def test_window_overlap_weights_quarter_hour_stagger() -> None:
    """Verify fractional supply window (09:15 to 17:15) accurately distributes fractional hour weights."""
    dates = pd.date_range("2024-01-01 00:00:00", "2024-01-01 23:00:00", freq="1h")
    weights = compute_supply_window_overlap_weights(dates, "09:15", "17:15")

    # Total duration must equal exactly 8.0 hours
    assert np.isclose(weights.sum(), 8.0, atol=1e-6)

    # Hour 9 (09:00 to 10:00) contains 45 minutes of window -> weight 0.75
    assert np.isclose(weights[dates.hour == 9].iloc[0], 0.75, atol=1e-6)
    # Hours 10 to 16 are fully inside -> weight 1.0
    for h in range(10, 17):
        assert np.isclose(weights[dates.hour == h].iloc[0], 1.0, atol=1e-6)
    # Hour 17 (17:00 to 18:00) contains 15 minutes of window -> weight 0.25
    assert np.isclose(weights[dates.hour == 17].iloc[0], 0.25, atol=1e-6)
    # Hour 18 is outside -> weight 0.0
    assert np.isclose(weights[dates.hour == 18].iloc[0], 0.0, atol=1e-6)
