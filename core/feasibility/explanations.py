"""Structured plain-language explanations and actionable remediation hints for feasibility screening.

Enforces PROJECT_SPEC Module 6 and Phase 3:
- Returns per rule: PASS or FAIL, computed value, threshold, and generated f-string explanation.
- Overall verdict: 'Feasible', 'Marginal' (fails only soft/warning rules), or 'Rejected' (fails blocking rules).
- Ranked list of rejection reasons sorted by severity and violation magnitude.
- Actionable remediation hints (e.g. maximum capacity land allows, transformer ceiling).
"""

from typing import Dict, Any, List


def generate_rule_explanation(
    rule_id: str,
    passed: bool,
    measured: float,
    operator: str,
    threshold: float,
    unit: str,
) -> str:
    """Generate dynamic narrative explanation with f-strings (no hardcoded numbers)."""
    if passed:
        if operator == "<=":
            return f"Measured value ({measured:.2f} {unit}) is within allowable ceiling ({threshold:.2f} {unit})."
        elif operator == ">=":
            return f"Measured value ({measured:.2f} {unit}) satisfies minimum requirement ({threshold:.2f} {unit})."
        elif operator == "==":
            return f"Measured value ({measured:.1f} {unit}) matches standard ({threshold:.1f} {unit})."
        else:
            return f"Condition satisfied ({measured:.2f} {operator} {threshold:.2f} {unit})."
    else:
        if rule_id == "RULE_SUBSTATION_DISTANCE_MAX":
            return f"Interconnection distance of {measured:.2f} km exceeds maximum allowable limit of {threshold:.2f} km."
        elif rule_id == "RULE_LAND_AVAILABILITY":
            return f"Available land ratio of {measured:.2f} falls below required minimum ratio of {threshold:.2f} ({measured*100:.1f}% available)."
        elif rule_id == "RULE_SOLAR_SHARE_TARGET":
            return f"Achieved annual solar share of {measured*100:.1f}% fails to meet target requirement of {threshold*100:.1f}%."
        elif rule_id == "RULE_TRANSFORMER_CAPACITY_RATIO":
            return f"Transformer loading ratio of {measured*100:.1f}% exceeds maximum allowable injection ceiling of {threshold*100:.1f}%."
        elif rule_id == "RULE_FINANCIAL_TARIFF_CEILING":
            return f"Levelized cost of ₹{measured:.2f}/kWh exceeds regulated grid tariff ceiling of ₹{threshold:.2f}/kWh."
        elif rule_id == "RULE_FINANCIAL_BUDGET":
            deficit = abs(measured)
            return f"Project capital expenditure exceeds user budget by ₹{deficit/1e5:.2f} Lakhs."
        elif rule_id == "RULE_UNMET_DEMAND_MAX":
            return f"Unmet irrigation demand of {measured*100:.1f}% exceeds reliability tolerance of {threshold*100:.1f}%."
        elif rule_id == "RULE_PLANT_CAPACITY_MAX":
            return f"Proposed capacity of {measured:.2f} MW exceeds scheme maximum ceiling of {threshold:.2f} MW."
        elif rule_id == "RULE_PLANT_CAPACITY_MIN":
            return f"Proposed capacity of {measured:.2f} MW is below scheme minimum threshold of {threshold:.2f} MW."
        elif rule_id == "RULE_SUPPLY_WINDOW_DURATION":
            return f"Supply window duration of {measured:.1f} hours does not equal the mandated {threshold:.1f} hours."
        elif rule_id == "RULE_EVACUATION_VOLTAGE":
            return f"Evacuation voltage of {measured:.0f} kV differs from standard {threshold:.0f} kV."
        elif rule_id == "RULE_PROJECT_COST_PER_MW_MAX":
            return f"Capital cost of ₹{measured/1e7:.2f} Cr/MWp exceeds benchmark ceiling of ₹{threshold/1e7:.2f} Cr/MWp."
        else:
            return f"Constraint violated: measured {measured:.2f} {unit} does not satisfy {operator} {threshold:.2f} {unit}."


def generate_feasibility_verdict(
    evaluation_results: List[Dict[str, Any]],
    scenario_params: Dict[str, float],
    land_requirement_acres_per_mw: float = 4.0,
    pt_capacity_mva: float = 5.0,
    transformer_power_factor: float = 0.95,
) -> Dict[str, Any]:
    """Compile structured feasibility determination, messages, ranked rejections, and remediation hints."""
    blocking_failures: List[Dict[str, Any]] = []
    warning_failures: List[Dict[str, Any]] = []
    remediation_hints: List[str] = []
    rule_table: List[Dict[str, Any]] = []

    def get_val(item: Any, key: str, default: Any = None) -> Any:
        if isinstance(item, dict):
            return item.get(key, default)
        return getattr(item, key, default)

    for res in evaluation_results:
        passed = bool(get_val(res, "passed", True))
        rule_id = str(get_val(res, "rule_id", ""))
        description = str(get_val(res, "description", ""))
        measured_val = float(get_val(res, "measured_value", 0.0))
        threshold_val = float(get_val(res, "threshold", 0.0))
        operator = str(get_val(res, "operator", ""))
        unit = str(get_val(res, "unit", ""))
        source = str(get_val(res, "source", ""))
        severity = str(get_val(res, "severity", "warning"))

        explanation = generate_rule_explanation(
            rule_id=rule_id,
            passed=passed,
            measured=measured_val,
            operator=operator,
            threshold=threshold_val,
            unit=unit,
        )

        item = {
            "rule_id": rule_id,
            "description": description,
            "status": "PASS" if passed else "FAIL",
            "passed": passed,
            "measured_value": measured_val,
            "threshold": threshold_val,
            "operator": operator,
            "unit": unit,
            "source": source,
            "severity": severity,
            "explanation": explanation,
            "message": f"[{rule_id}] {description} ({explanation}; Source: {source})",
        }
        rule_table.append(item)

        if not passed:
            # Calculate relative violation magnitude for ranking
            denom = abs(threshold_val) if abs(threshold_val) > 1e-4 else 1.0
            if operator in ("<=", "<"):
                violation_margin = (measured_val - threshold_val) / denom
            else:
                violation_margin = (threshold_val - measured_val) / denom

            item["violation_margin"] = violation_margin

            if severity == "blocking":
                blocking_failures.append(item)
            else:
                warning_failures.append(item)

    # Sort failures: higher violation margin first
    blocking_failures.sort(key=lambda x: x.get("violation_margin", 0.0), reverse=True)
    warning_failures.sort(key=lambda x: x.get("violation_margin", 0.0), reverse=True)

    # Ranked rejection reasons: blocking first, then warning
    ranked_rejection_reasons = blocking_failures + warning_failures

    # Remediation hints based on failures
    for item in ranked_rejection_reasons:
        rule_id = item["rule_id"]
        thresh = item["threshold"]
        if rule_id == "RULE_LAND_AVAILABILITY":
            avail_land = scenario_params.get("available_land_acres", 0.0)
            max_cap_land = avail_land / land_requirement_acres_per_mw if land_requirement_acres_per_mw > 0 else 0.0
            remediation_hints.append(
                f"Land constraint: Available candidate land ({avail_land:.1f} acres) supports a maximum solar plant capacity of {max_cap_land:.2f} MWp."
            )
        elif rule_id == "RULE_TRANSFORMER_CAPACITY_RATIO":
            max_safe_mw = pt_capacity_mva * transformer_power_factor * thresh
            remediation_hints.append(
                f"Transformer constraint: Limit proposed plant capacity to <= {max_safe_mw:.2f} MWp to prevent reverse power overloading on the {pt_capacity_mva:.1f} MVA transformer."
            )
        elif rule_id == "RULE_SUBSTATION_DISTANCE_MAX":
            remediation_hints.append(
                f"Interconnection distance: Select a candidate project site within {thresh:.1f} km of the 33/11 kV substation to comply with MSEDCL line loss standards."
            )
        elif rule_id == "RULE_PLANT_CAPACITY_MAX":
            remediation_hints.append(
                f"Regulatory ceiling: Reduce capacity to <= {thresh:.1f} MWp as mandated by PM-KUSUM Component C guidelines."
            )
        elif rule_id == "RULE_PLANT_CAPACITY_MIN":
            remediation_hints.append(
                f"Scheme threshold: Increase capacity to >= {thresh:.1f} MWp to qualify for PM-KUSUM feeder solarization."
            )
        elif rule_id == "RULE_SOLAR_SHARE_TARGET":
            remediation_hints.append(
                f"Solar share shortfall: Increase candidate solar capacity or add battery storage to reach the {thresh*100:.1f}% solar target."
            )
        elif rule_id == "RULE_FINANCIAL_BUDGET":
            remediation_hints.append(
                f"Budget constraint: Reduce solar/battery capacity or seek additional grant funding to match available capital budget."
            )

    if blocking_failures:
        overall_status = "Not Feasible"
        overall_verdict = "Rejected"
        summary_statement = f"Project is Rejected due to {len(blocking_failures)} blocking constraint violation(s)."
    elif warning_failures:
        overall_status = "Feasible with warnings"
        overall_verdict = "Marginal"
        summary_statement = f"Project is Marginal with {len(warning_failures)} non-blocking advisory note(s)."
    else:
        overall_status = "Feasible"
        overall_verdict = "Feasible"
        summary_statement = "Project is Feasible, satisfying all technical, regulatory, and financial criteria."

    total_rules = len(evaluation_results)
    total_passed = sum(1 for r in evaluation_results if get_val(r, "passed", True))

    return {
        "verdict": overall_verdict,
        "overall_status": overall_status,
        "summary_statement": summary_statement,
        "blocking_failures": blocking_failures,
        "warning_failures": warning_failures,
        "ranked_rejection_reasons": ranked_rejection_reasons,
        "remediation_hints": remediation_hints,
        "rule_table": rule_table,
        "total_rules_evaluated": total_rules,
        "rules_passed": total_passed,
        "total_passed": total_passed,
    }
