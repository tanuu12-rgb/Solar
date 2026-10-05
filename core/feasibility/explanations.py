"""Structured plain-language explanations and actionable remediation hints for feasibility screening.

Enforces PROJECT_SPEC Module 6:
- Overall status: 'Feasible', 'Feasible with warnings', 'Not Feasible'.
- Listing EVERY blocking failure with transparent citation.
- 'What would make this feasible' hints (e.g. maximum capacity land allows, transformer ceiling).
"""

from typing import Dict, Any, List


def generate_feasibility_verdict(
    evaluation_results: List[Dict[str, Any]],
    scenario_params: Dict[str, float],
    land_requirement_acres_per_mw: float = 4.0,
    pt_capacity_mva: float = 5.0,
    transformer_power_factor: float = 0.95,
) -> Dict[str, Any]:
    """Compile structured feasibility determination, messages, and actionable remediation hints."""
    blocking_failures = []
    warning_failures = []
    remediation_hints = []

    def get_val(item: Any, key: str, default: Any = None) -> Any:
        if isinstance(item, dict):
            return item.get(key, default)
        return getattr(item, key, default)

    for res in evaluation_results:
        passed = get_val(res, "passed", True)
        if not passed:
            rule_id = get_val(res, "rule_id", "")
            description = get_val(res, "description", "")
            measured_val = get_val(res, "measured_value", 0.0)
            threshold_val = get_val(res, "threshold", 0.0)
            operator = get_val(res, "operator", "")
            unit = get_val(res, "unit", "")
            source = get_val(res, "source", "")
            severity = get_val(res, "severity", "warning")

            msg = (
                f"[{rule_id}] {description} "
                f"(Measured: {measured_val} {unit}, Required: {operator} {threshold_val} {unit}; "
                f"Source: {source})"
            )
            item = {
                "rule_id": rule_id,
                "description": description,
                "measured_value": measured_val,
                "threshold": threshold_val,
                "operator": operator,
                "unit": unit,
                "source": source,
                "severity": severity,
                "explanation": f"Measured: {measured_val} {unit}, Required: {operator} {threshold_val} {unit}",
                "message": msg,
            }
            if severity == "blocking":
                blocking_failures.append(item)
            else:
                warning_failures.append(item)

    # Remediation hints based on failures
    for res in evaluation_results:
        passed = get_val(res, "passed", True)
        if not passed:
            rule_id = get_val(res, "rule_id", "")
            threshold_val = get_val(res, "threshold", 0.0)
            if rule_id == "RULE_LAND_AVAILABILITY":
                avail_land = scenario_params.get("available_land_acres", 0.0)
                max_cap_land = avail_land / land_requirement_acres_per_mw if land_requirement_acres_per_mw > 0 else 0.0
                remediation_hints.append(
                    f"Land constraint: Available candidate land ({avail_land:.1f} acres) supports a maximum solar plant capacity of {max_cap_land:.2f} MWp."
                )

            elif rule_id == "RULE_TRANSFORMER_CAPACITY_RATIO":
                max_safe_mw = pt_capacity_mva * transformer_power_factor * threshold_val
                remediation_hints.append(
                    f"Transformer constraint: Limit proposed plant capacity to <= {max_safe_mw:.2f} MWp to prevent reverse power overloading on the {pt_capacity_mva:.1f} MVA transformer."
                )

            elif rule_id == "RULE_SUBSTATION_DISTANCE_MAX":
                remediation_hints.append(
                    f"Interconnection distance: Select a candidate project site within {threshold_val} km of the 33/11 kV substation to comply with MSEDCL line loss standards."
                )

            elif rule_id == "RULE_PLANT_CAPACITY_MAX":
                remediation_hints.append(
                    f"Regulatory ceiling: Reduce capacity to <= {threshold_val} MWp as mandated by PM-KUSUM Component C guidelines."
                )

            elif rule_id == "RULE_PLANT_CAPACITY_MIN":
                remediation_hints.append(
                    f"Scheme threshold: Increase capacity to >= {threshold_val} MWp to qualify for PM-KUSUM feeder solarization."
                )

    if blocking_failures:
        overall_status = "Not Feasible"
        summary_statement = f"Project is NOT FEASIBLE due to {len(blocking_failures)} blocking constraint violation(s)."
    elif warning_failures:
        overall_status = "Feasible with warnings"
        summary_statement = f"Project is FEASIBLE WITH WARNINGS ({len(warning_failures)} non-blocking advisory note(s))."
    else:
        overall_status = "Feasible"
        summary_statement = "Project satisfies ALL technical, regulatory, and land interconnection criteria."

    total_rules = len(evaluation_results)
    total_passed = sum(1 for r in evaluation_results if get_val(r, "passed", True))

    return {
        "overall_status": overall_status,
        "summary_statement": summary_statement,
        "blocking_failures": blocking_failures,
        "warning_failures": warning_failures,
        "remediation_hints": remediation_hints,
        "total_rules_evaluated": total_rules,
        "rules_passed": total_passed,
        "total_passed": total_passed,
    }
