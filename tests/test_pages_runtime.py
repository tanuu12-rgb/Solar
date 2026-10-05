"""Runtime execution test for all Streamlit pages to ensure zero exceptions."""

from __future__ import annotations

import sys
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.state import get_illustrative_scenario_inputs, ScenarioInputs
from core.data.loaders import load_feeder_schedule, load_weather_data, load_crop_parameters
from core.demand.crop_water import calculate_daily_crop_water_requirements
from core.demand.pump_energy import calculate_pump_energy_from_volume
from core.demand.hourly_profile import build_hourly_irrigation_demand_profile
from core.solar.pv_model import simulate_pv_generation
from core.solar.dispatch import simulate_hourly_dispatch
from core.feasibility.rules_engine import evaluate_feasibility_rules, select_transmission_voltage
from core.feasibility.explanations import generate_feasibility_verdict
from core.gis.route import calculate_connection_route
from core.solar.optimizer import calculate_annualized_system_cost
from core.emissions import calculate_avoided_emissions
from core.config_loader import get_assumption_value


def test_feasibility_and_summary_report_runtime():
    """Verify all calculations on Page 4 and Page 6 execute cleanly with illustrative scenario."""
    inputs = get_illustrative_scenario_inputs()
    schedule_df = load_feeder_schedule()
    weather_df = load_weather_data()
    crop_params_df = load_crop_parameters()

    feeder_row = schedule_df.iloc[0]

    # Demand
    daily_water_df = calculate_daily_crop_water_requirements(
        weather_df=weather_df,
        crop_mix_ha=inputs.crop_mix_ha,
        crop_params_df=crop_params_df,
        irrigation_methods=inputs.irrigation_methods,
    )
    _, daily_water_df["e_el_kwh"] = calculate_pump_energy_from_volume(
        daily_water_df["total_water_volume_m3"]
    )
    hourly_demand_df = build_hourly_irrigation_demand_profile(
        daily_demand_df=daily_water_df,
        hourly_timestamps=weather_df.index,
        window_start=feeder_row["window_start"],
        window_end=feeder_row["window_end"],
        connected_pump_capacity_kw=inputs.connected_pump_kw,
    )

    # Solar
    solar_df = simulate_pv_generation(
        weather_df=weather_df,
        solar_capacity_mwp=inputs.candidate_solar_mwp,
    )

    # Dispatch
    dispatch_df, dispatch_metrics = simulate_hourly_dispatch(
        solar_generation_kwh=solar_df["solar_generation_kwh"],
        pump_demand_kwh=hourly_demand_df["pump_served_kwh"],
        battery_capacity_mwh=inputs.candidate_battery_mwh,
    )

    # Feasibility (Page 4 logic)
    pt_mva = float(feeder_row["pt_capacity_mva"])
    land_req_per_mw = float(get_assumption_value("land_requirement_acres_per_mw") or get_assumption_value("land_requirement_acres_per_mwp"))
    cand_solar = inputs.candidate_solar_mwp or 0.0
    dist_km = inputs.distance_to_substation_km or 0.0
    candidate_land_ratio = inputs.available_land_acres / (cand_solar * land_req_per_mw)
    transformer_loading_ratio = cand_solar / (pt_mva * 0.95)
    solar_capex_per_mwp = float(get_assumption_value("solar_capex_per_mwp") or get_assumption_value("solar_capex_per_mwp_inr"))
    batt_capex_per_mwh = float(get_assumption_value("battery_capex_per_mwh") or get_assumption_value("battery_capex_per_mwh_inr"))

    selected_voltage_kv = select_transmission_voltage(cand_solar, dist_km)
    total_capex = cand_solar * solar_capex_per_mwp + (inputs.candidate_battery_mwh or 0.0) * batt_capex_per_mwh
    budget_surplus = (inputs.budget_inr - total_capex) if inputs.budget_inr is not None else 0.0

    achieved_solar_share = dispatch_metrics["solar_share_percent"] / 100.0
    unmet_demand_fraction = hourly_demand_df["pump_unmet_kwh"].sum() / max(1.0, hourly_demand_df["pump_demand_kwh"].sum())

    measured_params = {
        "solar_plant_mw": cand_solar,
        "distance_to_substation_km": dist_km,
        "candidate_land_ratio": candidate_land_ratio,
        "transformer_loading_ratio": transformer_loading_ratio,
        "window_duration_hours": 8.0,
        "evacuation_voltage_kv": selected_voltage_kv,
        "solar_capex_per_mwp_inr": solar_capex_per_mwp,
        "solar_share_fraction": achieved_solar_share,
        "budget_surplus_inr": budget_surplus,
        "unmet_demand_fraction": unmet_demand_fraction,
    }
    context_vars = {
        "available_land_acres": inputs.available_land_acres,
        "pt_capacity_mva": pt_mva,
    }
    evaluations = evaluate_feasibility_rules(measured_params)
    verdict = generate_feasibility_verdict(evaluations, context_vars)
    assert verdict["verdict"] in ("Feasible", "Marginal", "Rejected")

    # Route & Summary (Page 6 logic)
    route_res = calculate_connection_route(
        plant_lat=inputs.plant_lat or 18.3950,
        plant_lon=inputs.plant_lon or 76.5520,
        substation_lat=inputs.substation_lat or 18.3800,
        substation_lon=inputs.substation_lon or 76.5400,
        plant_mw=cand_solar,
        hourly_solar_generation_kwh=solar_df["solar_generation_kwh"],
    )
    assert route_res.route_km > 0
    assert route_res.peak_loss_kw >= 0

    cost_res = calculate_annualized_system_cost(
        solar_capacity_mwp=cand_solar,
        battery_capacity_mwh=inputs.candidate_battery_mwh or 0.0,
        grid_imported_kwh=dispatch_metrics["grid_imported_kwh"],
    )
    assert cost_res["total_annualized_cost_inr"] > 0
    assert cost_res["cost_per_kwh_solar_served_inr"] > 0

    emiss_res = calculate_avoided_emissions(
        solar_energy_used_kwh=dispatch_metrics["total_solar_served_kwh"],
        grid_imported_kwh=dispatch_metrics["grid_imported_kwh"],
        total_demand_kwh=dispatch_metrics["total_demand_kwh"],
    )
    avoided_co2 = emiss_res.get("avoided_t_co2", 0.0)
    residual_co2 = emiss_res.get("residual_t_co2", 0.0)
    residual_grid_dep = emiss_res.get("residual_grid_dependence_pct", 0.0)
    assert avoided_co2 >= 0
    assert residual_co2 >= 0
    assert 0.0 <= residual_grid_dep <= 100.0
