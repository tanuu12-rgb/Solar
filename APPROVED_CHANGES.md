# APPROVED CHANGES LOG

This file logs all approved architectural, configuration, and implementation changes across all development phases, adhering strictly to `PROJECT_SPEC.md` and user instructions.

---

## Phase 0: System & Dataset Audit (Completed)
- **Code Changes:** None (audit phase only).
- **Environment Verification:** Python 3.14.7 on Windows. Verified imports of `pandas` (3.0.6), `pvlib` (0.16.1), `scipy` (1.18.1), `plotly` (7.1.0), `streamlit` (1.65.0), `pydeck` (0.9.3), `pydantic` (2.13.5), `PyYAML` (6.0.3). Installed `pypdf` (6.19.0) and `networkx` (3.7) in `.venv`.
- **Test Suite Status:** 49/49 tests passing in `pytest -v` (0 failures, 0 errors).
- **Hardcoded Defaults Cataloged:** Identified in `app/state.py` (ScenarioInputs field defaults) and `app/pages/1_Inputs_and_Data.py` (fallback 20.0 ha and "drip" method).
- **Datasets Inspected:**
  1. `open-meteo-18.38N76.54E633m.csv`: 8,784 hourly IST rows for 2024.
  2. `POWER_Point_Hourly_2024*.csv` (6 files): 8,784 hourly LST rows, zero -999 flags. Monthly GHI cross-check with Open-Meteo performed (annual difference 3.84%, mean monthly abs diff 7.63 kWh/m²).
  3. `crop_params.csv`: 5 crops with FAO-56 stage lengths and Kc values. Identified wheat season crossing calendar year boundary (Nov 15 + 120 days).
  4. `feeder_schedule.csv`: 3 feeders for 33/11 kV Bhatangali, all with 8-hour supply windows and 2.5 MW solar plant capacity.
  5. `2011-12_Irrigation_Area_Latur.zip`: Unzipped to `data/raw/extracted/`. Handled Ahmadpur duplicate (TALUKA_ID 4228). Computed district-level crop shares: Soybean 1.45%, Gram 18.64%, Sugarcane 46.36%, Tur 10.68%, Wheat 22.87%.
  6. `Ltr-to-field_KUSUM-C_Daytime-Ag_06.08.24-1.pdf`: Text extracted and searched. Contains policy conditions, 8-hour supply rules, and Annexure-A substation table; does NOT contain per-feeder connected load, HP, kW, or consumer counts.

---

## Phase 1: Input Honesty & Sourced Defaults (Completed)
- **Code Changes:**
  - `app/state.py`: Removed all hardcoded defaults from `ScenarioInputs`. Added fields: `crop_mix_source`, `command_area_ha`, `plant_lat`, `plant_lon`, `substation_lat`, `substation_lon`, `budget_inr`, and `is_illustrative`. Pre-filled `candidate_solar_mwp` strictly from `feeder_schedule.csv`. Added `get_illustrative_scenario_inputs()` and `render_scenario_banner()`. Updated cached runners to validate inputs strictly and raise `MissingInputError`.
  - `app/pages/1_Inputs_and_Data.py`: Added top scenario banner, visible "Load illustrative scenario" button, crop-mix source selection radio (Manual vs. District-Proxy scaled to command area), removed 20.0 ha fallback, and replaced hardcoded narrative text with dynamic f-string evaluations.
  - `app/pages/2_Irrigation_Demand.py`, `3_Solar_and_Battery_Sizing.py`, `4_Feasibility.py`, `5_Summary_Report.py`: Added persistent scenario banner and input validation. In Page 3, made plant evaluation headers and narrative dynamic.
  - `core/demand/crop_water.py`: Updated `calculate_fao56_kc_curve()` to handle calendar year boundary wrap-around for winter Rabi crops (e.g. Wheat).
  - `config/assumptions.yaml`: Codified `crop_calendar_boundary_convention: "wrap_around"` with citation to FAO-56 Section 6.
  - `core/data/loaders.py`: Added `load_district_proxy_crop_shares()` and `calculate_district_proxy_crop_mix()`.
  - `tests/test_data_loaders.py`: Added `test_load_district_proxy_crop_shares()`.
  - `tests/test_demand.py`: Added `test_crop_kc_calendar_year_boundary_wrap()`.
- **Test Suite Status:** 51/51 tests passing in `pytest -v` (0 failures, 0 errors).

## Phase 2: Cost Model & Cost-Optimal Sizing (Completed)
- **Code Changes:**
  - `config/assumptions.yaml`: Codified all 13 Phase 2 cost parameters: `solar_capex_per_mwp` (40,000,000 INR/MWp, MERC benchmark), `solar_om_fraction_of_capex` (0.0125, MERC tariff order), `battery_capex_per_mwh` (18,000,000 INR/MWh, CEA/SECI), `battery_om_fraction_of_capex` (0.02, SECI standard terms), `discount_rate` (0.09, MERC WACC), `project_lifetime_years` (25 yr, MSEDCL PPA), `battery_lifetime_years` (10 yr, BNEF/CEA), `battery_replacement_cost_fraction_of_capex` (0.60, NREL ATB), `grid_tariff_per_kwh` (4.50 INR/kWh, MERC retail tariff), `line_capex_per_km_11kv` (800,000 INR/km, MSEDCL Cost Data Book), `line_capex_per_km_33kv` (1,500,000 INR/km, MSEDCL Cost Data Book), `substation_bay_cost` (2,500,000 INR, MSEDCL bay schedule of rates), `land_cost_per_acre` (500,000 INR/acre, Maharashtra Ready Reckoner).
  - `core/config_loader.py`: Updated `STAGE_REQUIRED_ASSUMPTIONS["stage_5"]` and `stage_6` to include all Phase 2 cost parameters while maintaining backwards-compatible legacy key checks.
  - `core/solar/optimizer.py`: Extended `calculate_annualized_system_cost()` to compute annual solar capex via CRF + O&M, annual battery capex via CRF + replacement + O&M, annual grid purchase cost, and total annualized cost per kWh solar served. Enhanced `run_capacity_optimization_sweep()` to return clear narrative messages for unreachable targets (`results_df.attrs["unreachable_message"]`), and implemented `calculate_command_area_for_target_share()` using deterministic bisection search over demand scaling factors. Added `get_missing_cost_assumptions()`.
  - `app/pages/2_Irrigation_Demand.py`: Fixed monthly summary aggregation column name from `'effective_rain_mm'` to `'peff_mm'`.
  - `app/pages/3_Solar_and_Battery_Sizing.py`: Added headline cost-optimal sizing recommendation banner with 4 primary KPI metrics, missing cost assumption warnings, cost vs. solar-share frontier scatter plot, MWp × MWh annualized cost heatmap, and Section 5 inverse sizing calculator.
  - `tests/test_emissions.py`: Added 4 tests: `test_optimizer_is_deterministic`, `test_optimizer_resimulation_reproduces_target_share`, `test_optimizer_unreachable_target_returns_message`, and `test_inverse_command_area_monotonicity_and_reproduction`.
- **Test Suite Status:** 55/55 tests passing in `pytest -v` (0 failures, 0 errors).

## Phase 3: Feasibility with Rejection Reasons (Completed)
- **Code Changes:**
  - `config/rules.yaml`: Added all statutory and engineering rules: `RULE_SOLAR_SHARE_TARGET`, `RULE_SUBSTATION_DISTANCE_MAX`, `RULE_LAND_AVAILABILITY`, `RULE_EVACUATION_VOLTAGE`, `RULE_TRANSFORMER_CAPACITY_RATIO`, `RULE_FINANCIAL_TARIFF_CEILING`, `RULE_FINANCIAL_BUDGET`, `RULE_UNMET_DEMAND_MAX`, `RULE_PLANT_CAPACITY_MIN`, `RULE_PLANT_CAPACITY_MAX`, `RULE_SUPPLY_WINDOW_DURATION`, and `RULE_PROJECT_COST_PER_MW_MAX`.
  - `core/feasibility/rules_engine.py`: Added `select_transmission_voltage(solar_plant_mw, distance_km)` to select 11 kV vs 33 kV per MSEDCL guidelines. Enforced `MissingInputError` on null rule thresholds.
  - `core/feasibility/explanations.py`: Implemented `generate_rule_explanation()` to produce f-string generated narrative sentences without hardcoded numbers. Implemented three-tier verdict determination (`Feasible`, `Marginal`, `Rejected`) and ranked rejection reasons sorted by severity and violation margin. Added actionable remediation hints.
  - `app/pages/4_Feasibility.py`: Implemented full-width verdict banner (🟢 Feasible, 🟡 Marginal, 🔴 Rejected) with dynamic f-string summary, 4 KPI cards, ranked rejection list, remediation guidance, and detailed screening table.
  - `tests/test_feasibility.py`: Added `test_select_transmission_voltage()`, `test_feasibility_marginal_verdict_soft_rule_failure()`, and `test_feasibility_ranked_rejection_reasons()`.
- **Test Suite Status:** 58/58 tests passing in `pytest -v` (0 failures, 0 errors).

## Phase 4: GIS Connection Route Module (Completed)
- **Code Changes:**
  - `config/assumptions.yaml`: Added Section 8 GIS parameters: `gis_route_factor` (1.25, CBIP transmission manual), `line_resistance_per_km_11kv_ohm` (0.54 Ohm/km, ACSR Racoon), `line_resistance_per_km_33kv_ohm` (0.27 Ohm/km, ACSR Panther), `line_reactance_per_km_11kv_ohm` (0.38 Ohm/km), `line_reactance_per_km_33kv_ohm` (0.35 Ohm/km), `gis_grid_cell_size_deg` (0.005 deg), and `gis_obstacle_cost_multiplier` (100.0).
  - `core/gis/__init__.py` & `core/gis/route.py`: Created complete GIS connection route module implementing:
    - Great-circle Haversine distance calculation (labelled straight-line lower bound).
    - Voltage selection (11 kV vs 33 kV).
    - Optional GeoJSON obstacle avoidance using 2D raster least-cost path optimization with `networkx`.
    - Three-phase $I^2R$ peak electrical loss (kW), annual energy loss (MWh), and loss percentage (%) using hourly generation profiles.
    - Infrastructure capital expenditure calculation (line capex + substation bay expansion cost).
    - Standard GeoJSON `FeatureCollection` generation with LineString route and Point markers.
  - `tests/test_gis.py`: Added 4 tests: `test_haversine_known_coordinates()`, `test_losses_increase_with_distance()`, `test_cost_scales_linearly_with_length()`, and `test_obstacle_path_never_shorter_than_straight_line()`.
- **Test Suite Status:** 62/62 tests passing in `pytest -v` (0 failures, 0 errors).

## Phase 5: Emissions & Grid Dependence (Completed)
- **Code Changes:**
  - `core/emissions.py`: Extended `calculate_avoided_emissions()` to report avoided carbon emissions ($t\text{CO}_2$), residual grid imported energy ($\text{MWh}$), residual carbon emissions ($t\text{CO}_2$), and residual grid dependence percentage ($\%$ of annual irrigation demand).
  - `tests/test_emissions.py`: Added `test_calculate_residual_emissions_and_grid_dependence()`.
## Phase 6: Executive Summary Report & Multi-Format Data Export (Completed)
- **Code Changes:**
  - `app/pages/6_Summary_Report.py`: Created comprehensive executive brief synthesizing:
    - Project scope, 33/11 kV substation identification, and feeder operational window.
    - Statutory feasibility 3-tier verdict, passed rules ratio, blocking failures, and ranked rejection reasons with remediation hints.
    - GIS connection route metrics: distance (with method label), evacuation voltage, peak/annual $I^2R$ power & energy losses, and line CAPEX.
    - Full lifecycle economics: annualized solar CAPEX, annualized battery CAPEX, O&M, residual grid energy cost, total annualized project cost, and levelized cost per kWh solar served.
    - Physics & dispatch KPIs: pumping demand, solar generation, direct to demand, BESS discharge, total solar served, achieved solar share, residual grid import, curtailment, BESS curtailment avoided, and battery full equivalent cycles (EFC).
    - Environmental decarbonization metrics: avoided $t\text{CO}_2$/year, residual grid import emissions, and residual grid dependence %.
    - Downloadable exports: full 8,784-hour simulation time-series CSV and structured JSON executive project brief.
  - Removed redundant old page files (`5_Summary_Report.py`).

## Phase 7: Transparent Assumptions, Data Provenance, Theme & Documentation (Completed)
- **Code Changes:**
  - `app/theme.py`: Created centralized application theme with Inter typography, design palette (`#0B3C5D` DISCOM blue, `#F2A900` solar amber, `#2E7D32` agriculture green, `#F8FAFC` background), card containers, and status chips.
  - `app/state.py`: Updated `get_dataset_provenance()` to include full audit metadata for all 7 raw datasets (`open-meteo-18.38N76.54E633m.csv`, `feeder_schedule.csv`, `crop_params.csv`, `2011-12_Irrigation_Area_Latur.zip`, `2011-12_Production_Crops_Latur.zip`, `Ltr-to-field_KUSUM-C_Daytime-Ag_06.08.24-1.pdf`, `POWER_Point_Hourly_*.csv`) with SHA-256 cryptographic hashes and `Active` vs `Check-Only` pipeline statuses.
  - `app/pages/7_Assumptions_and_Sources.py`: Created complete audit dashboard with:
    - Color-coded status chips (`SOURCED`, `USER-ENTERED`, `ILLUSTRATIVE`, `CHECK-ONLY`, `MISSING`).
    - Searchable assumptions audit table (Key, Value, Unit, Type, Cited Source, Engineering Rationale).
    - Regulatory feasibility rules audit table (ID, Description, Operator, Threshold, Severity, Regulation).
    - Local datasets provenance table with file sizes and SHA-256 integrity hashes.
    - Deterministic Engineering Physics vs. Machine Learning Architecture Note explaining why first-principles models are mandatory for DISCOM statutory planning, alongside future ML research opportunities (satellite NDVI crop calibration, nowcasting solar forecasting, and physics-informed neural networks).
  - Applied `apply_theme()` across `app/main.py` and `app/pages/1` through `7`.
  - Updated `README.md` with complete architecture, setup instructions, and test verification.
- **Test Suite Status:** 63/63 tests passing in `pytest -v` (0 failures, 0 errors).

