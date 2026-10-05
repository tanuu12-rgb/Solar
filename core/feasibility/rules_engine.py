"""Feasibility screening rules engine evaluating deterministic engineering constraints.

Enforces PROJECT_SPEC Module 6:
- Pure rule-based screening without ML or black-box heuristics.
- Evaluates candidate scenario against rules in config/rules.yaml.
- Evaluates pass/fail, measured value, threshold, unit, source, severity.
"""

from typing import Dict, Any, List
import pandas as pd

from core.config_loader import ConfigLoader, RuleEntry, default_config_loader
from core.errors import RuleEvaluationError


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
    """Evaluate all rules in config/rules.yaml against provided scenario parameters.

    Parameters expected:
    - solar_plant_mw: Candidate plant DC capacity (MW).
    - distance_to_substation_km: Distance to substation (km).
    - candidate_land_ratio: available_acres / required_acres.
    - transformer_loading_ratio: solar_plant_mw / (pt_capacity_mva * pf).
    - window_duration_hours: Feeder supply window duration (h).
    - evacuation_voltage_kv: Interconnection voltage (kV, default 11.0).
    - solar_capex_per_mwp_inr: Project Capex per MWp (INR).
    """
    rules = loader.load_raw_rules()
    evaluation_results = []

    for rule in rules:
        param_name = rule.parameter
        if param_name not in parameters_dict:
            raise RuleEvaluationError(
                f"Missing evaluated parameter '{param_name}' for rule '{rule.id}'"
            )

        measured_val = float(parameters_dict[param_name])
        threshold_val = float(rule.threshold) if rule.threshold is not None else 0.0

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
            "notes": rule.notes,
        })

    return evaluation_results
