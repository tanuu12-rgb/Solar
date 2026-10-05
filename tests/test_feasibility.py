"""Unit tests for the deterministic regulatory feasibility screening engine."""

from core.feasibility.rules_engine import evaluate_feasibility_rules
from core.feasibility.explanations import generate_feasibility_verdict


def test_feasibility_all_passing() -> None:
    """Verify that a compliant candidate configuration yields an overall FEASIBLE verdict."""
    params = {
        "solar_plant_mw": 2.5,
        "distance_to_substation_km": 1.8,
        "candidate_land_ratio": 1.5,  # 50% more land than minimum
        "transformer_loading_ratio": 0.55,  # 55% loading (< 100%)
        "window_duration_hours": 8.0,
        "evacuation_voltage_kv": 11.0,
        "solar_capex_per_mwp_inr": 40000000.0,
    }
    context = {"available_land_acres": 15.0, "pt_capacity_mva": 5.0}

    evals = evaluate_feasibility_rules(params)
    verdict = generate_feasibility_verdict(evals, context)

    assert verdict["overall_status"] == "Feasible"
    assert len(verdict["blocking_failures"]) == 0


def test_feasibility_blocking_failure_insufficient_land() -> None:
    """Verify that insufficient land triggers a blocking failure and generates remediation hint."""
    params = {
        "solar_plant_mw": 5.0,
        "distance_to_substation_km": 1.5,
        "candidate_land_ratio": 0.5,  # Only half the required land!
        "transformer_loading_ratio": 0.6,
        "window_duration_hours": 8.0,
        "evacuation_voltage_kv": 11.0,
        "solar_capex_per_mwp_inr": 40000000.0,
    }
    context = {"available_land_acres": 10.0, "pt_capacity_mva": 5.0}

    evals = evaluate_feasibility_rules(params)
    verdict = generate_feasibility_verdict(evals, context)

    assert verdict["overall_status"] == "Not Feasible"
    assert len(verdict["blocking_failures"]) >= 1
    assert any(bf["rule_id"] == "RULE_LAND_AVAILABILITY" for bf in verdict["blocking_failures"])
    assert len(verdict["remediation_hints"]) >= 1


def test_feasibility_substation_distance_blocking() -> None:
    """Verify that excessive distance to substation (> 5 km) triggers blocking failure."""
    params = {
        "solar_plant_mw": 2.0,
        "distance_to_substation_km": 8.5,  # > 5.0 km threshold
        "candidate_land_ratio": 1.2,
        "transformer_loading_ratio": 0.5,
        "window_duration_hours": 8.0,
        "evacuation_voltage_kv": 11.0,
        "solar_capex_per_mwp_inr": 40000000.0,
    }
    context = {"available_land_acres": 12.0, "pt_capacity_mva": 5.0}

    evals = evaluate_feasibility_rules(params)
    verdict = generate_feasibility_verdict(evals, context)

    assert verdict["overall_status"] == "Not Feasible"
    assert any(bf["rule_id"] == "RULE_SUBSTATION_DISTANCE_MAX" for bf in verdict["blocking_failures"])
