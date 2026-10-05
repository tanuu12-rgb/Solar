"""Unit tests for typed error classes."""

import pytest
from core.errors import (
    FeederSolarError,
    MissingInputError,
    DataValidationError,
    EnergyBalanceError,
    RuleEvaluationError,
)


def test_missing_input_error() -> None:
    """Verify MissingInputError sets key and informative message."""
    err = MissingInputError("test_key")
    assert isinstance(err, FeederSolarError)
    assert err.key == "test_key"
    assert "test_key" in str(err)

    custom_err = MissingInputError("another_key", "Custom explanation message")
    assert custom_err.key == "another_key"
    assert "Custom explanation message" in str(custom_err)


def test_data_validation_error() -> None:
    """Verify DataValidationError formats timestamps when provided."""
    timestamps = ["2024-01-01 00:00", "2024-01-01 01:00"]
    err = DataValidationError("Found -999 fill values", timestamps=timestamps)
    assert isinstance(err, FeederSolarError)
    assert err.timestamps == timestamps
    assert "Found -999 fill values" in str(err)
    assert "2024-01-01 00:00" in str(err)


def test_energy_balance_error() -> None:
    """Verify EnergyBalanceError captures imbalance and tolerance."""
    err = EnergyBalanceError(imbalance_kwh=12.5, tolerance_kwh=0.01)
    assert isinstance(err, FeederSolarError)
    assert err.imbalance_kwh == 12.5
    assert err.tolerance_kwh == 0.01
    assert "12.500000 kWh exceeds tolerance of 0.010000 kWh" in str(err)


def test_rule_evaluation_error() -> None:
    """Verify RuleEvaluationError captures rule_id and reason."""
    err = RuleEvaluationError("RULE_PLANT_CAPACITY_MIN", "Parameter 'solar_plant_mw' not provided")
    assert isinstance(err, FeederSolarError)
    assert err.rule_id == "RULE_PLANT_CAPACITY_MIN"
    assert "RULE_PLANT_CAPACITY_MIN" in str(err)
