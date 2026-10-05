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


def test_select_transmission_voltage() -> None:
    """Verify transmission voltage selection logic (11 kV vs 33 kV)."""
    from core.feasibility.rules_engine import select_transmission_voltage

    # <= 3 MW and <= 5 km -> 11 kV
    assert select_transmission_voltage(2.5, 3.0) == 11.0
    assert select_transmission_voltage(3.0, 5.0) == 11.0

    # > 3 MW -> 33 kV
    assert select_transmission_voltage(4.0, 2.0) == 33.0

    # > 5 km -> 33 kV
    assert select_transmission_voltage(2.0, 7.5) == 33.0


def test_feasibility_marginal_verdict_soft_rule_failure() -> None:
    """Verify that failing only soft/warning rules results in MARGINAL verdict."""
    params = {
        "solar_plant_mw": 2.5,
        "distance_to_substation_km": 2.0,
        "candidate_land_ratio": 1.5,
        "transformer_loading_ratio": 0.5,
        "window_duration_hours": 8.0,
        "evacuation_voltage_kv": 11.0,
        "solar_capex_per_mwp_inr": 40000000.0,
        "solar_share_fraction": 0.80,
        "budget_surplus_inr": 1000000.0,
        "cost_per_kwh_solar_served_inr": 5.20,  # > 4.50 ceiling (soft rule)
        "unmet_demand_fraction": 0.08,  # > 0.05 limit (soft rule)
    }
    context = {"available_land_acres": 15.0, "pt_capacity_mva": 5.0}

    evals = evaluate_feasibility_rules(params)
    verdict = generate_feasibility_verdict(evals, context)

    assert verdict["verdict"] == "Marginal"
    assert len(verdict["blocking_failures"]) == 0
    assert len(verdict["warning_failures"]) >= 1
    assert len(verdict["ranked_rejection_reasons"]) >= 1


def test_feasibility_ranked_rejection_reasons() -> None:
    """Verify that rejection reasons are ranked with blocking failures prioritized."""
    params = {
        "solar_plant_mw": 2.5,
        "distance_to_substation_km": 7.0,  # Blocking failure
        "candidate_land_ratio": 0.6,  # Blocking failure
        "transformer_loading_ratio": 0.5,
        "window_duration_hours": 8.0,
        "evacuation_voltage_kv": 11.0,
        "solar_capex_per_mwp_inr": 40000000.0,
        "solar_share_fraction": 0.80,
        "budget_surplus_inr": 500000.0,
        "cost_per_kwh_solar_served_inr": 5.00,  # Warning failure
    }
    context = {"available_land_acres": 6.0, "pt_capacity_mva": 5.0}

    evals = evaluate_feasibility_rules(params)
    verdict = generate_feasibility_verdict(evals, context)

    assert verdict["verdict"] == "Rejected"
    assert verdict["overall_status"] == "Not Feasible"
    reasons = verdict["ranked_rejection_reasons"]
    assert len(reasons) >= 3
    # Blocking failures come before warning failures
    assert reasons[0]["severity"] == "blocking"
    assert reasons[1]["severity"] == "blocking"
    assert reasons[-1]["severity"] == "warning"

