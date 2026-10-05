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

---

