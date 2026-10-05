"""Unit tests for data loading and data validation modules."""

import pytest
import pandas as pd

from core.data.loaders import (
    load_weather_data,
    load_feeder_schedule,
    load_crop_parameters,
)
from core.data.validators import validate_weather_dataset
from core.errors import DataValidationError


def test_load_weather_data_integrity() -> None:
    """Verify Open-Meteo weather dataset loads with 8,784 hourly rows and no nulls."""
    df = load_weather_data()
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 8784
    assert df.isna().sum().sum() == 0

    expected_cols = [
        "temperature_2m",
        "precipitation",
        "et0_fao_evapotranspiration",
        "relative_humidity_2m",
        "wind_speed_10m",
        "shortwave_radiation",
        "direct_normal_irradiance",
        "diffuse_radiation",
    ]
    for col in expected_cols:
        assert col in df.columns, f"Missing expected column '{col}'"

    # Index must be DatetimeIndex covering full 2024 leap year
    assert df.index[0] == pd.Timestamp("2024-01-01 00:00:00")
    assert df.index[-1] == pd.Timestamp("2024-12-31 23:00:00")


def test_load_feeder_schedule_bhatangali() -> None:
    """Verify feeder schedule loads for 33/11 kV Bhatangali with exactly 8.0h supply windows."""
    df = load_feeder_schedule()
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 3

    assert (df["substation"] == "33/11 kV Bhatangali").all()
    assert (df["pt_capacity_mva"] == 5.0).all()
    assert (df["solar_plant_mw"] == 2.5).all()

    # Verify window duration is exactly 8.0 hours for all feeders
    for _, row in df.iterrows():
        start_h, start_m = map(int, row["window_start"].split(":"))
        end_h, end_m = map(int, row["window_end"].split(":"))
        duration = (end_h * 60 + end_m - (start_h * 60 + start_m)) / 60.0
        assert duration == 8.0, f"Feeder {row['feeder_name']} window duration is not 8h ({duration}h)"


def test_load_crop_parameters() -> None:
    """Verify FAO-56 crop parameters load with positive stage lengths and valid Kc."""
    df = load_crop_parameters()
    assert isinstance(df, pd.DataFrame)
    assert len(df) >= 5

    required_crops = {"Soybean", "Gram", "Sugarcane", "Tur", "Wheat"}
    assert required_crops.issubset(set(df["crop"].tolist()))

    for _, row in df.iterrows():
        assert row["l_ini"] > 0
        assert row["l_dev"] > 0
        assert row["l_mid"] > 0
        assert row["l_end"] > 0
        assert 0.0 < row["kc_ini"] < 2.0
        assert 0.0 < row["kc_mid"] < 2.0
        assert 0.0 < row["kc_end"] < 2.0


def test_validate_weather_dataset_bounds() -> None:
    """Verify sanity checks for weather dataset against regional reference ranges."""
    df = load_weather_data()
    metrics = validate_weather_dataset(df)

    assert "annual_rainfall_mm" in metrics
    assert "annual_ghi_kwh_per_m2" in metrics
    assert "annual_et0_mm" in metrics

    # SECI solar resource assessment for Marathwada: 1800 - 2200 kWh/m2
    assert 1800.0 <= metrics["annual_ghi_kwh_per_m2"] <= 2200.0
    # FAO-56 reference ET0 for semi-arid tropics: 1400 - 1900 mm
    assert 1400.0 <= metrics["annual_et0_mm"] <= 1900.0


def test_weather_validator_raises_on_invalid_bounds() -> None:
    """Verify DataValidationError is raised if weather data has impossible negative values."""
    df = load_weather_data().copy()
    df.loc[df.index[10], "shortwave_radiation"] = -50.0  # Physically impossible GHI

    with pytest.raises(DataValidationError):
        validate_weather_dataset(df)
