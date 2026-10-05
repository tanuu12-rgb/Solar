"""Typed error classes for Smart Feeder Solarization Planning and Decision Support System.

Fail loudly per PROJECT_SPEC Section 0 Rule 3:
Missing or malformed inputs raise typed exceptions and show clear error context.
Never use fillna, dropna, bare except, or silent defaults.
"""

from typing import Any, List, Optional


class FeederSolarError(Exception):
    """Base exception class for all errors in the Feeder Solarization DSS."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class MissingInputError(FeederSolarError):
    """Raised when a required config key, user input, or dataset is missing or empty.

    Per PROJECT_SPEC Section 0 Rule 2:
    'If a needed entry has an empty value or source, raise MissingInputError naming the exact key.'
    """

    def __init__(self, key: str, message: Optional[str] = None) -> None:
        self.key = key
        msg = message or f"Missing required input or unpopulated config key: '{key}'"
        super().__init__(msg)


class DataValidationError(FeederSolarError):
    """Raised when input data violates structural, physical, or temporal integrity checks.

    Per PROJECT_SPEC Section 3 and Section 7:
    Flags invalid row counts, duplicate timestamps, missing intervals, or -999 fill values.
    """

    def __init__(
        self,
        message: str,
        timestamps: Optional[List[str]] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        self.timestamps: List[str] = timestamps or []
        self.details: dict[str, Any] = details or {}
        if self.timestamps:
            sample = self.timestamps[:10]
            suffix = f" (affected timestamps: {', '.join(sample)}{'...' if len(self.timestamps) > 10 else ''})"
            formatted_msg = f"{message}{suffix}"
        else:
            formatted_msg = message
        super().__init__(formatted_msg)


class EnergyBalanceError(FeederSolarError):
    """Raised when hourly or annual energy balance is violated beyond configured tolerance.

    Per PROJECT_SPEC Section 5 Module 4:
    'Energy balance check on every run (generation + grid + battery discharge =
     served + charge + curtailed + losses, within a tolerance in config); raise an error if violated.'
    """

    def __init__(
        self,
        imbalance_kwh: float | str,
        tolerance_kwh: Optional[float] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        if isinstance(imbalance_kwh, str):
            self.imbalance_kwh = 0.0
            self.tolerance_kwh = tolerance_kwh or 0.0
            self.details = details or {}
            super().__init__(imbalance_kwh)
        else:
            self.imbalance_kwh = float(imbalance_kwh)
            self.tolerance_kwh = float(tolerance_kwh) if tolerance_kwh is not None else 0.0
            self.details = details or {}
            msg = (
                f"Energy balance violation: imbalance of {self.imbalance_kwh:.6f} kWh "
                f"exceeds tolerance of {self.tolerance_kwh:.6f} kWh."
            )
            super().__init__(msg)



class RuleEvaluationError(FeederSolarError):
    """Raised when a feasibility rule fails to evaluate due to missing parameters or invalid operators."""

    def __init__(self, rule_id: str, reason: str) -> None:
        self.rule_id = rule_id
        self.reason = reason
        super().__init__(f"Rule evaluation failed for '{rule_id}': {reason}")
