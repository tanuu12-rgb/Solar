# ऊर्जाSetu: Smart Feeder Solarization Planning & Decision Support System (Latur, Maharashtra)

An engineering decision-support tool for planning dedicated agricultural feeder solarization, battery storage sizing, connection routing, and regulatory feasibility screening under PM-KUSUM Component C guidelines in Latur District, Maharashtra.

---

## 1. Project Overview

This decision support system models:
1. **Real Agronomic Water & Pumping Demand**: FAO-56 dual crop coefficient ($K_c$) evapotranspiration, USDA effective rainfall, static groundwater depth (CGWB), total dynamic head (TDH), and pump electrical demand strictly constrained to 8-hour feeder supply windows.
2. **Solar PV Generation Aligned to IST**: Ground-mounted solar PV simulation with `pvlib`, Hay-Davies transposition, and Faiman cell temperature modeling.
3. **Battery Energy Storage System (BESS) Dispatch**: Hourly dispatch simulation with C-rate limits, round-trip efficiency, state-of-charge tracking, cycle counting, and zero-tolerance energy conservation.
4. **Lifecycle Cost Optimization**: Capital Recovery Factor (CRF) annualized CAPEX, OPEX, and residual grid cost minimization across solar MWp and battery MWh sizing sweeps, with deterministic bisection search for target solar share.
5. **GIS Grid Evacuation Route & Losses**: Haversine distance, right-of-way routing, automatic 11 kV vs 33 kV voltage selection, 3-phase $I^2R$ peak and annual electrical loss modeling, and line infrastructure cost estimation.
6. **Deterministic Regulatory Feasibility Screening**: 3-tier verdict (`Feasible`, `Marginal`, `Rejected`) with ranked statutory rejection reasons, parameter shortfall explanations, and actionable remediation hints based on MSEDCL circulars and PM-KUSUM guidelines.
7. **Transparent Data Provenance & Decarbonization**: Full cryptographic SHA-256 dataset tracking, avoided $t\text{CO}_2$ emissions benchmarked against CEA grid baselines, and complete assumptions audit.

---

## 2. Windows Environment Setup

### Prerequisites
- Python 3.11+ (Python 3.14 / 3.11 verified on Windows 64-bit)
- PowerShell or Windows Command Prompt

### Virtual Environment & Dependencies
```powershell
# Create virtual environment
py -m venv .venv

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Upgrade pip and install pinned dependencies
python -m pip install -r requirements.txt
```

### Running Tests
```powershell
.\.venv\Scripts\pytest.exe -v
```

### Running the Streamlit Application
```powershell
.\.venv\Scripts\streamlit.exe run app/main.py
```

---

## 3. Project Architecture

```
feeder_solar/
  PROJECT_SPEC.md                      # Engineering specification and non-negotiable rules
  APPROVED_CHANGES.md                  # Detailed chronological change log
  README.md                            # Documentation and setup instructions
  requirements.txt                     # Pinned core dependencies
  pytest.ini                           # Pytest configuration
  config/
    assumptions.yaml                   # 72 physical, financial, agronomic, and engineering assumptions
    rules.yaml                         # Statutory feasibility screening rules with severity tags
  core/
    __init__.py
    errors.py                          # Typed domain errors (MissingInputError, DataValidationError, etc.)
    config_loader.py                   # Pydantic v2 configuration parser and stage validator
    units.py                           # Physical constants and unit conversion equations
    data/
      loaders.py                       # Raw dataset loaders (Open-Meteo, Crop Params, Feeder Schedules)
      validators.py                    # Dataset validation checks (8,784 h, -999 checks, duplicates)
      time_alignment.py                # Hourly time alignment and feeder supply window overlap weights
    demand/
      crop_water.py                    # FAO-56 daily ETc, effective rainfall, NIR and GIR
      pump_energy.py                   # Hydraulic head and pump electrical energy
      hourly_profile.py                # Distribution over feeder supply window
    solar/
      pv_model.py                      # Transposition and temperature-corrected PV generation
      battery.py                       # BESS SoC tracking and efficiency
      dispatch.py                      # Hourly dispatch, curtailment, and energy balance
      optimizer.py                     # Capacity grid sweep and cost minimization
      sensitivity.py                   # One-at-a-time sensitivity analysis
    feasibility/
      rules_engine.py                  # Regulatory and technical rule evaluator
      explanations.py                  # Structured explanation generator & ranked rejection reasons
    gis/
      __init__.py
      route.py                         # Haversine distance, voltage selection, line capex, 3-phase I²R losses
    emissions.py                       # CEA grid emissions and grid dependence calculations
  app/
    main.py                            # Streamlit landing page with case study highlights
    theme.py                           # Centralized CSS stylesheet, color tokens, and UI badge chips
    state.py                           # Centralized state management, data caching, and simulation runners
    pages/
      1_Inputs_and_Data.py             # Feeder selection, crop mix, pump capacity, and window coverage
      2_Irrigation_Demand.py           # Seasonal crop water requirements, Kc curves, and hourly pump load
      3_Solar_and_Battery_Sizing.py    # Generation profiles, hero mismatch, BESS dispatch, and optimizer sweep
      4_Feasibility.py                 # Deterministic regulatory screening, 3-tier verdict, and remediation
      5_Connection_Route.py            # GIS evacuation route, PyDeck map, voltage selection, and line losses
      6_Summary_Report.py              # Executive one-page brief and CSV/JSON data export
      7_Assumptions_and_Sources.py     # Transparent assumptions audit, 7 raw dataset hashes, and ML architecture note
  data/
    raw/                               # 7 raw data assets (weather, schedules, crop params, census, policy)
  tests/                               # Pytest suite with 63 comprehensive unit tests
```

---

## 4. Key Engineering Capabilities

- **Staggered Agricultural Feeder Windows**: Models MSEDCL 8-hour daytime supply schedules (e.g. 06:00–14:00, 08:00–16:00, 10:00–18:00) and quantifies solar window capture ratios.
- **Strict Input Honesty**: Zero silent defaults. If agricultural crop hectares or pump ratings are unconfigured, the system prompts the user or offers a 1-click illustrative scenario toggle.
- **Comprehensive Lifecycle Cost Model**: Incorporates solar CAPEX, BESS initial CAPEX, battery replacement at end of life, annual O&M, and grid power purchase tariffs.
- **Deterministic Feasibility Verdict**: Evaluates power transformer headroom, land availability, distance to substation, daytime window duration, evacuation voltage, and capex budget.
- **Physical Loss Modeling**: Calculates 3-phase $I^2R$ power evacuation losses and energy dissipation based on conductor electrical resistance.

---

## 5. Test Suite Verification

Run all unit tests via pytest:
```powershell
.\.venv\Scripts\pytest.exe -v
```
All 63 unit tests pass across configuration loading, data ingestion, demand calculations, solar transposition, battery dispatch physics, feasibility rules, GIS routing, and cost optimization.
