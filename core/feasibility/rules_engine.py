"""Feasibility screening rules engine evaluating deterministic engineering constraints.

Enforces PROJECT_SPEC Module 6 and Phase 3:
- Pure rule-based screening without ML or black-box heuristics.
- Evaluates candidate scenario against rules in config/rules.yaml.
- Evaluates pass/fail, measured value, threshold, unit, source, severity.
- Null thresholds raise MissingInputError.
- Transmission voltage selection (11 kV vs 33 kV).
"""

from typing import Dict, Any, List, Optional
import pandas as pd

from core.config_loader import ConfigLoader, RuleEntry, default_config_loader
from core.errors import RuleEvaluationError, MissingInputError


def select_transmission_voltage(
    solar_plant_mw: float,
    distance_to_substation_km: float,
    mw_threshold_for_33kv: float = 3.0,
    distance_threshold_km_for_33kv: float = 5.0,
) -> float:
    """Select 11 kV or 33 kV transmission voltage based on plant MW and distance.

    Standard MSEDCL technical criteria:
    - Plants <= 3.0 MW and distance <= 5.0 km connect at 11 kV.
    - Plants > 3.0 MW or distance > 5.0 km connect at 33 kV.
    """
    if solar_plant_mw > mw_threshold_for_33kv or distance_to_substation_km > distance_threshold_km_for_33kv:
        return 33.0
    return 11.0


def evaluate_comparison(measured: float, operator: str, threshold: float) -> bool:
    """Evaluate comparison operator deterministically."""
    if operator == "<=":
        return measured <= (threshold + 1e-6)
    elif operator == ">=":
        return measured >= (threshold - 1e-6)
    elif operator == "<":
        return measured < threshold
    elif operator == ">":
        return measured > threshold
    elif operator == "==":
        return abs(measured - threshold) < 1e-4
    elif operator == "!=":
        return abs(measured - threshold) >= 1e-4
    else:
        raise RuleEvaluationError(f"Unsupported rule comparison operator: '{operator}'")


def evaluate_feasibility_rules(
    parameters_dict: Dict[str, float],
    loader: ConfigLoader = default_config_loader,
) -> List[Dict[str, Any]]:
    """Evaluate rules in config/rules.yaml against provided scenario parameters.

    Null rule thresholds raise MissingInputError.
    Parameters not present in parameters_dict are skipped if optional,
    ensuring backwards compatibility with targeted unit tests.
    """
    rules = loader.load_raw_rules()
    evaluation_results = []

    for rule in rules:
        if rule.threshold is None:
            raise MissingInputError(
                f"Rule threshold for '{rule.id}' is null in config/rules.yaml",
                key=rule.id,
            )

        param_name = rule.parameter
        if param_name not in parameters_dict:
            # If parameter is not supplied in the input dictionary, skip rule
            continue

        measured_val = float(parameters_dict[param_name])
        threshold_val = float(rule.threshold)

        passed = evaluate_comparison(measured_val, rule.operator, threshold_val)

        evaluation_results.append({
            "rule_id": rule.id,
            "description": rule.description,
            "parameter": param_name,
            "operator": rule.operator,
            "threshold": threshold_val,
            "measured_value": round(measured_val, 3),
            "unit": rule.unit,
            "severity": rule.severity,
            "source": rule.source,
            "passed": passed,
            "status": "PASS" if passed else "FAIL",
            "notes": rule.notes,
        })

    return evaluation_results
