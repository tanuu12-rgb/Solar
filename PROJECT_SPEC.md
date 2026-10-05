# PROJECT SPEC: Smart Feeder Solarization Planning and Decision Support System (Latur, Maharashtra)

You are a senior Python engineer with domain knowledge in power systems, agronomy (FAO-56) and data engineering. Build the project described here, **one stage at a time** (Section 9). Follow every rule literally. If this document conflicts with your habits, this document wins. If something required is missing or ambiguous, **do not invent a value: stop, list exactly what is missing, and ask.**

Platform: **Windows**. Use `pathlib.Path` with paths relative to the project root. Never hardcode `C:\` paths or backslashes. Open all text files with explicit `encoding="utf-8"` and handle `\r\n` line endings.

---

## 0. NON-NEGOTIABLE RULES

1. **No dummy, random, mock, placeholder or synthetic data anywhere** (code, UI, app tests). Do not import `random` or use `np.random`. No hardcoded sample arrays. No fake fallback values.
2. **No hidden numbers.** Every physical, financial or policy constant lives in `config/assumptions.yaml` or `config/rules.yaml`. Each entry has: `value`, `unit`, `source` (document + section, or URL), `type` (`sourced` or `assumption`), `notes`. If a needed entry has an empty `value` or `source`, raise `MissingInputError` naming the exact key. **Never fill these in yourself.** Create the templates with empty fields and list them for me. (Only exceptions: mathematical/physical constants such as g = 9.81 m/s², water density 1000 kg/m³.)
3. **Fail loudly.** Missing/malformed files raise typed exceptions (`MissingInputError`, `DataValidationError`) and show a clear UI error. Never use `fillna`, `dropna`, bare `except`, or silent defaults to get past a problem. If rows are removed for a documented reason (Section 3), log the count and show it in the UI.
4. **Provenance.** Every number in the UI traces to a dataset, a config key, or a rule id. Build an "Assumptions and Data Sources" page listing every config entry (flagged `sourced` / `assumption`) and every dataset loaded (file name, row count, date range, SHA-256).
5. **Units in names and checks:** `_kw`, `_kwh`, `_mwp`, `_mm`, `_m3`, `_km`. Never mix kW and kWh.
6. **Deterministic.** Same inputs, same outputs.
7. **Explainability.** Every decision returns a structured explanation, not only a label.
8. **Quality:** Python 3.11, type hints, docstrings stating formulas and sources, `pydantic` v2 models, `logging` (no prints), `pytest`.
9. **Disclaimer in the UI footer:** this is an early-stage decision-support tool, not a replacement for detailed DISCOM engineering studies. Also state that the weather is a single historical year (2024) and that crop areas are 2011-12 taluka-level statistics.

---

## 1. SCOPE (what to build, what NOT to build)

**Build (core):** data loading and validation, irrigation energy demand, solar generation, battery dispatch, capacity optimizer, rule-based feasibility screening, Streamlit dashboard.

**Build only if I explicitly ask (stretch):** GIS route optimization (Section 5, Module 7).

**Do NOT build:** any machine-learning model, any forecasting model, EV/flexible-load/neighbour-substation redistribution, any blockchain or "AI" features. CO₂ is a single one-line output only.

**Case study:** one Latur substation taken from `data/raw/feeder_schedule.csv` (I will choose which). The tool must work for the substation and taluka that appear in that file, not for a hardcoded one.

**Headline findings the dashboard must surface (computed from real data, never typed in):**
1. Share of annual solar energy that falls inside each feeder's supply window (the windows are staggered; late windows such as 10:00 to 18:00 capture much less sunshine than 08:00 to 16:00).
2. Seasonal mismatch: monthly solar generation vs monthly irrigation demand (surplus in monsoon, shortfall in dry months).
3. Curtailment avoided: energy curtailed under a naive baseline dispatch vs the optimized configuration.

---

## 2. TECH STACK

Python 3.11, `streamlit`, `plotly`, `pandas`, `numpy`, `scipy`, `pvlib`, `pydantic` v2, `pyyaml`, `pytest`. Create a virtual environment (`.venv`) and pin versions in `requirements.txt`.
**Do not include** `geopandas`, `osmnx`, `shapely`, `networkx`, `scikit-learn`, `shap` until the GIS stretch is requested (they are hard to install on Windows and would block Stage 1).

---

## 3. LOCAL DATASETS (the only data source; do NOT call any weather API)

Project root is `feeder_solar/`; data is in `data/raw/`. Keep original file names. Read zips directly without extracting.

1. **`POWER_Point_Hourly_2024*.csv` (6 files).** Text header ending with `-END HEADER-`; parse the CSV after it (sort files by date range). Columns: `YEAR, MO, DY, HR, ALLSKY_SFC_SW_DWN` (Wh/m²). Time standard: **LST (local solar time), not IST**. Lat 18.38, Lon 76.54. **Only GHI is present** (no temperature, wind, DNI or DHI). Validate: 8,784 contiguous hourly rows for 2024, no duplicates, no `-999` fill values (raise `DataValidationError` listing timestamps if any).
2. **`open-meteo-18_38N76_54E633m.csv`.** Lines 1 to 2 are metadata (latitude, longitude, elevation 633 m, `utc_offset_seconds` 19800), then a blank line, then the data table with columns: `time` (IST), `temperature_2m` (°C), `precipitation` (mm), `et0_fao_evapotranspiration` (mm), `relative_humidity_2m` (%), `wind_speed_10m` (km/h). Validate 8,784 hourly rows, no nulls. Hourly precipitation and ET₀ are per-hour amounts; **the interval convention (preceding hour vs following hour) must be a config key I confirm**, no default.
3. **`2011-12_Irrigation_Area_Latur.zip` (XML).** One `<IRRIGATION_AREA>` element per taluka with tags `<CROP>_AR_UNDER_CROP` and `<CROP>_AR_UNDER_IRR`. The loader must handle these known issues **explicitly and report them in the UI**:
   - (a) **Ahmadpur (`TALUKA_ID` 4228) appears twice.** Deduplicate on `TALUKA_ID`, assert the duplicate rows are identical, and log how many rows were removed.
   - (b) Elements with `Missing="."` are **missing values, not zeros.** Keep them as missing and show which taluka/crop cells are missing.
   - (c) **Area units are not stated in the file.** Read them from config key `crop_area_unit` (I must confirm it; no default).
4. **`2011-12_Production_Crops_Latur.zip`:** present but **not used** in any calculation. Do not load it.
5. **`feeder_schedule.csv`** (I transcribe Annexure-A of MSEDCL letter `CE(PP)/LM/AgLM/KUSUM-C/24355`, 06.08.2024). Columns: `district, taluka, substation, pt_capacity_mva, solar_plant_mw, feeder_name, feeder_type, window_start, window_end` (times as `HH:MM`; windows include quarter-hour offsets such as 07:30, 09:15, 09:45). **Pump supply hours come ONLY from this file.** Validate that each window is 8 hours.

**Time alignment (critical):**
- NASA is local solar time (UTC + longitude/15 h ≈ UTC + 5.10 h); Open-Meteo is IST (UTC + 5.5 h). They differ by about 24 minutes.
- Convert NASA to IST using an **energy-conserving** method (shift the interval, then time-weighted resample to hourly). Do not join on raw timestamps. Do not interpolate irradiance values naively.
- The NASA hour convention (hour-beginning / centred / hour-ending) must be a config key `nasa_hour_convention` that I confirm; no default.
- Supply windows with 15/30/45-minute offsets must be applied as **fractional-hour overlap weights** per hour.
- Implement a unit test showing total GHI energy is conserved after the conversion.

**Data-quality page (page 1)** must show for every dataset: row count, date range, missing counts, issues found and how they were handled.

**Sanity checks to display (warn, never silently adjust):**
- Annual and monthly rainfall from Open-Meteo, with a config-driven reference range for Latur. I suspect the 2024 total is high; show it and let me compare it with IMD data.
- Annual GHI (kWh/m²) and annual ET₀ (mm).

---

## 4. PROJECT STRUCTURE

```
feeder_solar/
  PROJECT_SPEC.md
  README.md
  requirements.txt
  .gitignore
  app/
    main.py
    pages/
      1_Inputs_and_Data.py
      2_Irrigation_Demand.py
      3_Solar_and_Battery_Sizing.py
      4_Feasibility.py
      5_Summary_Report.py
      6_Assumptions_and_Sources.py
  core/
    errors.py
    config_loader.py
    units.py
    data/
      loaders.py
      validators.py
      time_alignment.py
    demand/
      crop_water.py
      pump_energy.py
      hourly_profile.py
    solar/
      pv_model.py
      battery.py
      dispatch.py
      optimizer.py
      sensitivity.py
    feasibility/
      rules_engine.py
      explanations.py
    emissions.py
  config/
    assumptions.yaml
    rules.yaml
  data/
    raw/
  tests/
```

---

## 5. MODULES

### Module 1: Inputs and Configuration (page 1)
Choose the substation/feeder from `feeder_schedule.csv` (taluka comes from that row, which selects the crop data). Inputs: irrigated area per crop served by the feeder (ha), planting dates, irrigation method per crop, connected pump capacity (kW), target solar share of annual irrigation energy, candidate site land (acres), battery on/off. **Feeder-level irrigated area and connected pump capacity are NOT in any dataset**: they must be user inputs with a stated source/assumption (if I have not provided them, raise `MissingInputError`; never derive them silently from the taluka total). Validate with pydantic; share one `ScenarioInputs` object across pages.

### Module 2: Irrigation Energy Demand
1. **ET₀:** use `et0_fao_evapotranspiration` from the Open-Meteo file (aggregate to daily). Do not implement Penman-Monteith unless I ask.
2. **Crop evapotranspiration:** `ETc = Kc(t) × ET0`. Kc curve from stage lengths and planting date, linear interpolation per FAO-56. Kc values, stage lengths and planting dates come from `data/raw/crop_params.csv`, which **I must supply** (FAO-56 Tables 11/12 and local calendar); if missing, raise `MissingInputError`. Never embed Kc values in code.
3. **Effective rainfall:** one method (USDA SCS or FAO-56 dependable rain), chosen in config with a source.
4. **Net irrigation requirement:** `NIR_mm = max(0, ETc − Peff)` daily.
5. **Gross requirement:** `GIR_mm = NIR_mm / irrigation_efficiency` (by method, from config).
6. **Volume:** `V_m3 = GIR_mm × 10 × area_ha`.
7. **Pump energy:** `E_hyd_kwh = ρ g H V / 3.6e6`; `E_el_kwh = E_hyd_kwh / (η_pump × η_motor)`. Total dynamic head `H` (groundwater depth + drawdown + friction) and efficiencies come from config with sources (head should come from CGWB depth-to-water data that I supply). Never default them.
8. **Hourly profile:** distribute daily electrical energy over the feeder's **real supply window** (fractional-hour weights). If the daily requirement exceeds what the window can deliver at the connected pump capacity, report it as **unmet demand**; never scale silently.

Outputs: daily/monthly tables, annual MWh, per-crop breakdown, seasonal chart.

### Module 3: Solar Generation (`pvlib`)
- GHI (after alignment) to DNI/DHI via `pvlib.irradiance.erbs`; transposition to plane-of-array with the model, tilt and azimuth set in config.
- Cell temperature from Open-Meteo temperature and wind (10 m wind, converted per config), using the model/parameters in config.
- DC/AC chain with temperature coefficient, DC losses, inverter efficiency, soiling, availability, degradation, all from config.
- Output per-kWp hourly AC profile, scaled to candidate capacity.
- **Mandatory validation card:** annual specific yield (kWh/kWp) and CUF%, with the config-driven expected range for the region and a warning if outside it.
- **Window coverage analysis:** for every feeder in `feeder_schedule.csv`, compute the percentage of annual (and per-month) solar energy that falls inside its supply window. This is a headline finding.

### Module 4: Battery and Dispatch
Hourly simulation over the year:
- Solar serves pump load directly within the supply window; surplus charges the battery (power limits, round-trip efficiency, SoC limits from config); deficit is served by battery, then grid.
- Export/evacuation limit comes from the transformer rating in `feeder_schedule.csv` (`pt_capacity_mva`) and the power-factor/loading limits in config. Energy beyond what the battery and the limit can absorb is **curtailed**.
- Run solar-only and solar+battery.
- Metrics: solar share of demand, residual grid dependence (% and MWh), curtailment (% and MWh), battery equivalent full cycles, unmet demand.
- **Curtailment-avoided metric:** compare against a baseline rule defined in config (naive dispatch: no battery, fixed priority). Report curtailed energy under baseline vs optimized configuration.
- **Energy balance check on every run** (generation + grid + battery discharge = served + charge + curtailed + losses, within a tolerance in config); raise an error if violated.
- Also evaluate the **actually commissioned plant** (`solar_plant_mw` from the schedule file) as a scenario: how much of the feeder's irrigation energy does it cover inside the window?

### Module 5: Optimizer, Sensitivity, Emissions
- Sweep solar capacity (MWp) and battery capacity (MWh); ranges and steps from config.
- Constraint: solar share of annual irrigation energy >= user target. Objective: minimise annualised cost (capex × CRF + O&M), formula documented. Capex, O&M, discount rate, lifetime from config with sources.
- Return best feasible configuration, the full result grid, the cost-vs-share view, and an explicit message if no configuration in the sweep meets the target.
- One-at-a-time sensitivity (solar capacity, battery capacity, crop area, capex, tariff) as a tornado chart.
- Emissions: single line, `avoided_kg = solar_energy_used_kwh × grid_emission_factor` (factor from config, with the named CEA version).

### Module 6: Feasibility Screening (rule-based; no ML)
- Rules live in `config/rules.yaml` with: `id`, `description`, `parameter`, `operator`, `threshold`, `unit`, `source`, `severity` (`blocking`/`warning`). **Leave thresholds empty for me to fill from the MSEDCL letter and MNRE PM-KUSUM guidelines. Do not guess.**
- Candidate rule parameters: plant capacity range, distance to substation, land available vs land required per MW, plant size vs transformer rating, supply window = 8 hours, evacuation voltage level, project cost limits.
- Per rule: pass/fail, measured value, threshold, unit, source, plain-language message. Overall: `Feasible` / `Feasible with warnings` / `Not Feasible`, listing **every** blocking failure.
- Add "what would make this feasible" hints (for example, the maximum capacity the available land allows).
- Present it as a rule engine, not as AI.

### Module 7: GIS Route Optimization (STRETCH, do not build until I ask)
When requested: OSM roads, `power=line`/`minor_line`/`substation`, land-use, water and protected areas via `osmnx` (cache queries); edge cost = length × line cost per km × land-use multiplier + crossing penalty (all from config); route with A* or Dijkstra; compare against straight-line distance; compute line losses `3·I²·R·L`; show a folium map. First verify OSM has usable substation/line coverage for the area; if not, say so and stop. Never generate a synthetic route.

---

## 6. DASHBOARD (Streamlit)

- **Page 1 Inputs and Data:** scenario inputs, data-quality summary (Section 3), all dataset issues and how they were handled.
- **Page 2 Irrigation Demand:** Kc curves, monthly demand, seasonal view, annual energy KPI, rainfall/ET₀ sanity checks.
- **Page 3 Solar and Battery Sizing:** window-coverage chart for the feeders, monthly solar vs demand (surplus vs shortfall) as the hero chart, recommended capacity, cost grid, solar-only vs solar+battery, curtailment baseline vs optimized, tornado sensitivity, CUF validation card, existing-plant coverage.
- **Page 4 Feasibility:** status badge, rule table with reasons and sources, hints.
- **Page 5 Summary Report:** one-page summary; export CSV/JSON.
- **Page 6 Assumptions and Sources:** every config entry and every dataset.
- Plotly with labelled units. Cache heavy computations with `st.cache_data`. Large KPI cards at top; plain-language labels first (for example, "Farmers get daytime power"), technical terms second.

---

## 7. TESTS (pytest)

- Hand-calculated or published-example cases for: hydraulic energy, CRF, battery energy balance, window-overlap weights, GHI energy conservation after LST to IST alignment.
- Tests that: missing config values raise `MissingInputError`; `-999` raises `DataValidationError`; the Ahmadpur duplicate is detected and removed once; missing XML values are not turned into zeros; no module imports `random`.
- Literal expected values are allowed in tests only if each has a comment citing the hand calculation or published source. Never reuse them inside the app.

---

## 8. FIRST-RUN VERIFICATION (must print and show in the UI)

- NASA: 8,784 rows, 2024-01-01 to 2024-12-31, 0 fill values.
- Open-Meteo: 8,784 rows, 0 nulls.
- Irrigation XML: row count before and after deduplication (one fewer).
- `feeder_schedule.csv`: row count, every window = 8 h.
If any number differs, stop and report it. Do not continue.

---

## 9. BUILD ORDER

Build one stage at a time. After each stage: summarise what was built, list every assumption you needed, and list every config key I must fill. **Do not start the next stage until I confirm.**

1. Skeleton, config loader, error classes, empty `assumptions.yaml`/`rules.yaml` templates (list every key needed).
2. Data loaders, validators, time alignment; run the Section 8 checks.
3. Module 2 (demand) with tests.
4. Modules 3 and 4 (solar, window coverage, battery, dispatch) with tests.
5. Module 5 (optimizer, sensitivity, emissions).
6. Module 6 (feasibility).
7. Streamlit pages and report export.
8. README (setup on Windows, data requirements, limitations).
9. Module 7 only if I ask.

## 10. DEFINITION OF DONE

- Runs end to end for one Latur substation using only the local files plus the inputs I supplied.
- Search of the codebase finds no `random`, no hardcoded sample data, no numeric constants outside config (except physical/mathematical constants), and no `fillna`/`dropna`/bare `except` used to hide problems.
- Time-alignment, CUF, energy-balance and data-quality checks are visible in the UI.
- Every UI number is traceable to a dataset, config entry or rule.
- All tests pass.