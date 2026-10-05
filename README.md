# Smart Feeder Solarization Planning and Decision Support System (Latur, Maharashtra)

An engineering decision-support tool for planning dedicated agricultural feeder solarization and battery storage sizing under PM-KUSUM Component C guidelines in Latur District, Maharashtra.

---

## 1. Project Overview

This decision support system models:
1. Hourly agricultural water and pumping energy demand (FAO-56 crop evapotranspiration, CGWB groundwater head).
2. Ground-mounted solar PV generation aligned to Indian Standard Time (IST) using `pvlib`.
3. Battery energy storage system (BESS) dispatch, transformer evacuation limits, and curtailment avoidance.
4. Optimal capacity sizing (solar MWp and battery MWh) minimizing annualized system cost.
5. Rule-based regulatory and technical feasibility screening per MSEDCL and MNRE guidelines.
6. Interactive Streamlit dashboard for DISCOM engineers and planners.

---

## 2. Windows Environment Setup

### Prerequisites
- Python 3.11+ (Python 3.14 / 3.11 supported on Windows 64-bit)
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

---

## 3. Project Architecture

```
feeder_solar/
  PROJECT_SPEC.md                      # Engineering specification and non-negotiable rules
  README.md                            # Documentation and setup instructions
  requirements.txt                     # Pinned core dependencies
  .gitignore                           # Git ignore rules
  config/
    assumptions.yaml                   # Physical, financial, agronomic, and engineering assumptions
    rules.yaml                         # Rule-based feasibility screening limits
  core/
    __init__.py
    errors.py                          # Typed domain errors (MissingInputError, DataValidationError, etc.)
    config_loader.py                   # Pydantic v2 configuration parser and validator
    units.py                           # Physical constants and unit conversion equations
    data/
      loaders.py                       # Raw dataset loaders (NASA POWER, Open-Meteo, Crop XML, Feeder)
      validators.py                    # Dataset validation checks (8,784 h, -999 checks, duplicates)
      time_alignment.py                # Energy-conserving LST-to-IST conversion and window weights
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
      explanations.py                  # Structured explanation generator
    emissions.py                       # CEA grid emissions reduction calculation
  app/
    main.py                            # Streamlit entrypoint with disclaimer footer
    pages/
      1_Inputs_and_Data.py             # Scenario configuration and data quality cards
      2_Irrigation_Demand.py           # Seasonal demand profiles and sanity checks
      3_Solar_and_Battery_Sizing.py    # Generation profiles, hero comparison, and sizing grid
      4_Feasibility.py                 # Rule evaluation matrix and remediation hints
      5_Summary_Report.py              # Executive summary and export capabilities
      6_Assumptions_and_Sources.py     # Provenance table of all constants and datasets
  data/
    raw/                               # Local historical data repository
  tests/                               # Pytest suite with hand-calculated benchmarks
```

---

## 4. Current Status: Stage 1 Complete

Stage 1 (Skeleton, Config Loader, Error Classes, Empty Templates) has been successfully implemented and tested:
- Typed error classes created in `core/errors.py`.
- Physical constants and verified hand-calculated formulas implemented in `core/units.py`.
- Complete configuration templates created in `config/assumptions.yaml` and `config/rules.yaml` with all values left unpopulated per Section 0 Rule 2.
- Robust Pydantic v2 loader in `core/config_loader.py` enforcing strict missing key and unpopulated value detection.
- Full directory skeleton and module stubs generated.
- Test suite passing 15/15 tests including a codebase hygiene check preventing random/mock data generation.

---

## 5. Non-Negotiable Rules & Limitations

- **No Synthetic or Mock Data:** All computations rely exclusively on local historical files in `data/raw/` and user-provided inputs.
- **Fail Loudly:** Missing configuration keys, unpopulated parameters, or malformed data immediately raise typed errors.
- **Decision Support Disclaimer:** This tool provides early-stage decision support and does not replace comprehensive DISCOM power flow, transient stability, or detailed protection coordination studies.
