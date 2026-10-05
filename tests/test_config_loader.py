"""Unit tests for configuration loading and validation."""

from pathlib import Path
import shutil
import pytest
import yaml

from core.config_loader import (
    ConfigLoader,
    AssumptionEntry,
    load_assumptions,
    get_assumption,
    validate_assumption,
    validate_for_stage,
    load_rules,
    get_rule,
)
from core.errors import MissingInputError, DataValidationError


def test_load_assumptions_template() -> None:
    """Verify assumptions.yaml loads and all expected keys exist."""
    assumptions = load_assumptions()
    assert isinstance(assumptions, dict)
    assert len(assumptions) > 20

    # Check key representative assumptions
    expected_keys = [
        "interval_convention_open_meteo",
        "nasa_hour_convention",
        "crop_area_unit",
        "effective_rainfall_method",
        "irrigation_efficiency_drip",
        "groundwater_depth_m",
        "pv_tilt_deg",
        "battery_roundtrip_efficiency",
        "solar_capex_per_mwp_inr",
        "grid_emission_factor_kg_co2_per_kwh",
    ]
    for key in expected_keys:
        assert key in assumptions, f"Expected assumption key '{key}' missing from assumptions.yaml"
        entry = assumptions[key]
        assert hasattr(entry, "value")
        assert hasattr(entry, "unit")
        assert hasattr(entry, "source")
        assert hasattr(entry, "type")
        assert entry.type in ("sourced", "assumption")


def test_updated_key_types_and_notes() -> None:
    """Verify types and specific note contents in assumptions.yaml."""
    assumptions = load_assumptions()

    for k in assumptions:
        assert assumptions[k].type in ("sourced", "assumption"), f"Key '{k}' invalid type"

    # Check pv_azimuth_deg note contains required convention text
    azimuth_note = assumptions["pv_azimuth_deg"].notes
    assert "pvlib convention: 0 = north, 90 = east, 180 = south." in azimuth_note


def test_unpopulated_assumption_raises_missing_input_error() -> None:
    """Verify unpopulated assumptions raise MissingInputError naming the key."""
    dummy_entry = AssumptionEntry(
        value=None,
        unit="dimensionless",
        source="",
        type="assumption",
        notes="Unpopulated dummy entry",
    )
    with pytest.raises(MissingInputError) as exc_info:
        validate_assumption("unpopulated_test_key", dummy_entry, require_populated=True)

    assert exc_info.value.key == "unpopulated_test_key"
    assert "unpopulated_test_key" in str(exc_info.value)


def test_missing_config_key_raises_missing_input_error() -> None:
    """Verify requesting an unknown config key raises MissingInputError."""
    with pytest.raises(MissingInputError) as exc_info:
        get_assumption("completely_nonexistent_key_12345", require_populated=False)

    assert exc_info.value.key == "completely_nonexistent_key_12345"


def test_type_must_be_sourced_or_assumption() -> None:
    """Verify that type must be exactly 'sourced' or 'assumption'."""
    # Pydantic field validation
    with pytest.raises(ValueError, match="type must be exactly 'sourced' or 'assumption'"):
        AssumptionEntry(
            value=1.0,
            unit="dimensionless",
            source="Test Source",
            type="invalid_type",
            notes="test",
        )

    # ConfigLoader.validate_assumption check
    entry = AssumptionEntry.model_construct(
        value=1.0,
        unit="dimensionless",
        source="Test Source",
        type="other",
        notes="test",
    )
    with pytest.raises(DataValidationError, match="Must be exactly 'sourced' or 'assumption'"):
        validate_assumption("test_key", entry)


def test_sourced_type_with_empty_source_raises_missing_input_error() -> None:
    """Verify type='sourced' with empty source raises MissingInputError naming the key."""
    entry = AssumptionEntry(
        value="hour_beginning",
        unit="dimensionless",
        source="",
        type="sourced",
        notes="NASA POWER hour convention",
    )
    with pytest.raises(MissingInputError) as exc_info:
        validate_assumption("nasa_hour_convention", entry, require_populated=True)

    assert exc_info.value.key == "nasa_hour_convention"
    assert "nasa_hour_convention" in str(exc_info.value)
    assert "sourced" in str(exc_info.value)


def test_assumption_type_with_empty_source_raises_missing_input_error() -> None:
    """Verify type='assumption' still requires non-empty source as written justification."""
    entry = AssumptionEntry(
        value="usda_scs",
        unit="dimensionless",
        source="",
        type="assumption",
        notes="Effective rainfall choice",
    )
    with pytest.raises(MissingInputError) as exc_info:
        validate_assumption("effective_rainfall_method", entry, require_populated=True)

    assert exc_info.value.key == "effective_rainfall_method"
    assert "effective_rainfall_method" in str(exc_info.value)
    assert "assumption" in str(exc_info.value)


def test_allowed_string_values_validation() -> None:
    """Verify string-valued keys are restricted to their allowed sets."""
    # 1. nasa_hour_convention in {hour_beginning, centred, hour_ending}
    for valid_val in ("hour_beginning", "centred", "hour_ending"):
        entry = AssumptionEntry(
            value=valid_val,
            unit="dimensionless",
            source="NASA documentation",
            type="sourced",
            notes="test",
        )
        validate_assumption("nasa_hour_convention", entry, require_populated=True)

    invalid_nasa = AssumptionEntry(
        value="wrong_convention",
        unit="dimensionless",
        source="NASA documentation",
        type="sourced",
        notes="test",
    )
    with pytest.raises(DataValidationError, match="Invalid value 'wrong_convention' for 'nasa_hour_convention'"):
        validate_assumption("nasa_hour_convention", invalid_nasa, require_populated=True)

    # 2. interval_convention_open_meteo in {preceding_hour, following_hour}
    for valid_val in ("preceding_hour", "following_hour"):
        entry = AssumptionEntry(
            value=valid_val,
            unit="dimensionless",
            source="Open-Meteo API docs",
            type="sourced",
            notes="test",
        )
        validate_assumption("interval_convention_open_meteo", entry, require_populated=True)

    invalid_meteo = AssumptionEntry(
        value="instantaneous",
        unit="dimensionless",
        source="Open-Meteo API docs",
        type="sourced",
        notes="test",
    )
    with pytest.raises(DataValidationError, match="Invalid value 'instantaneous' for 'interval_convention_open_meteo'"):
        validate_assumption("interval_convention_open_meteo", invalid_meteo, require_populated=True)

    # 3. effective_rainfall_method in {usda_scs, fao_56_dependable}
    for valid_val in ("usda_scs", "fao_56_dependable"):
        entry = AssumptionEntry(
            value=valid_val,
            unit="dimensionless",
            source="FAO-56 Chapter 3",
            type="assumption",
            notes="test",
        )
        validate_assumption("effective_rainfall_method", entry, require_populated=True)

    invalid_rain = AssumptionEntry(
        value="penman_monteith",
        unit="dimensionless",
        source="FAO-56 Chapter 3",
        type="assumption",
        notes="test",
    )
    with pytest.raises(DataValidationError, match="Invalid value 'penman_monteith' for 'effective_rainfall_method'"):
        validate_assumption("effective_rainfall_method", invalid_rain, require_populated=True)


def test_load_rules_template() -> None:
    """Verify rules.yaml loads and all candidate rules exist with empty thresholds."""
    rules = load_rules()
    assert isinstance(rules, list)
    assert len(rules) >= 7

    rule_ids = {r.id for r in rules}
    expected_rule_ids = [
        "RULE_PLANT_CAPACITY_MIN",
        "RULE_PLANT_CAPACITY_MAX",
        "RULE_SUBSTATION_DISTANCE_MAX",
        "RULE_LAND_AVAILABILITY",
        "RULE_TRANSFORMER_CAPACITY_RATIO",
        "RULE_SUPPLY_WINDOW_DURATION",
    ]
    for r_id in expected_rule_ids:
        assert r_id in rule_ids, f"Expected rule id '{r_id}' missing from rules.yaml"


def test_unpopulated_rule_raises_missing_input_error(tmp_path: Path) -> None:
    """Verify unpopulated rules raise MissingInputError naming the rule id."""
    custom_cfg_dir = tmp_path / "config"
    custom_cfg_dir.mkdir(parents=True)
    shutil.copy("config/assumptions.yaml", custom_cfg_dir / "assumptions.yaml")

    rules_dict = {
        "rules": [
            {
                "id": "RULE_TEST_UNPOPULATED",
                "description": "Test unpopulated rule",
                "parameter": "test_param",
                "operator": ">=",
                "threshold": None,
                "unit": "MW",
                "source": "",
                "severity": "blocking",
            }
        ]
    }
    with open(custom_cfg_dir / "rules.yaml", "w", encoding="utf-8") as f:
        yaml.dump(rules_dict, f)

    loader = ConfigLoader(root_dir=tmp_path)
    with pytest.raises(MissingInputError) as exc_info:
        loader.get_rule("RULE_TEST_UNPOPULATED", require_populated=True)

    assert exc_info.value.key == "RULE_TEST_UNPOPULATED"


def test_validate_for_stage_stage2_passes_with_economics_keys_null(tmp_path: Path) -> None:
    """Verify validate_for_stage('stage2') passes when Stage 2 is populated and economics keys are null."""
    assumptions = load_assumptions()
    stage2_values = {
        "interval_convention_open_meteo": ("preceding_hour", "Open-Meteo documentation Section 2"),
        "nasa_hour_convention": ("hour_beginning", "NASA POWER methodology Section 3"),
        "crop_area_unit": ("hectare", "District Statistical Abstract Latur 2011-12"),
        "latur_annual_rainfall_reference_min_mm": (600.0, "IMD Pune district normals"),
        "latur_annual_rainfall_reference_max_mm": (950.0, "IMD Pune district normals"),
        "expected_annual_ghi_min_kwh_per_m2": (1800.0, "SECI regional solar resource assessment"),
        "expected_annual_ghi_max_kwh_per_m2": (2200.0, "SECI regional solar resource assessment"),
        "expected_annual_et0_min_mm": (1400.0, "FAO-56 agro-meteorological guidelines"),
        "expected_annual_et0_max_mm": (1900.0, "FAO-56 agro-meteorological guidelines"),
    }

    yaml_dict = {}
    for k, entry in assumptions.items():
        if k in stage2_values:
            val, src = stage2_values[k]
            yaml_dict[k] = {
                "value": val,
                "unit": entry.unit,
                "source": src,
                "type": entry.type,
                "notes": entry.notes,
            }
        else:
            # Leave economics and other keys completely null and unpopulated
            yaml_dict[k] = {
                "value": None,
                "unit": entry.unit,
                "source": "",
                "type": entry.type,
                "notes": entry.notes,
            }

    custom_cfg_dir = tmp_path / "config"
    custom_cfg_dir.mkdir(parents=True)
    with open(custom_cfg_dir / "assumptions.yaml", "w", encoding="utf-8") as f:
        yaml.dump(yaml_dict, f)
    shutil.copy("config/rules.yaml", custom_cfg_dir / "rules.yaml")

    loader = ConfigLoader(root_dir=tmp_path)
    # validate_for_stage('stage2') must pass with economics keys null
    loader.validate_for_stage("stage2")
    # Verify economics keys are indeed null
    raw = loader.load_raw_assumptions()
    assert raw["solar_capex_per_mwp_inr"].value is None
    assert raw["optimizer_objective"].value is None


def test_validate_for_stage_optimizer_raises_missing_input_error_naming_first_empty_key(tmp_path: Path) -> None:
    """Verify validate_for_stage('optimizer') raises MissingInputError naming the first empty key."""
    assumptions = load_assumptions()
    yaml_dict = {}
    for k, entry in assumptions.items():
        yaml_dict[k] = {
            "value": entry.value,
            "unit": entry.unit,
            "source": entry.source,
            "type": entry.type,
            "notes": entry.notes,
        }
    # Unpopulate a stage 5 key
    yaml_dict["solar_capex_per_mwp_inr"]["value"] = None
    yaml_dict["solar_capex_per_mwp_inr"]["source"] = ""

    custom_cfg_dir = tmp_path / "config"
    custom_cfg_dir.mkdir(parents=True)
    with open(custom_cfg_dir / "assumptions.yaml", "w", encoding="utf-8") as f:
        yaml.dump(yaml_dict, f)
    shutil.copy("config/rules.yaml", custom_cfg_dir / "rules.yaml")

    loader = ConfigLoader(root_dir=tmp_path)
    with pytest.raises(MissingInputError) as exc_info:
        loader.validate_for_stage("optimizer")

    assert exc_info.value.key == "solar_capex_per_mwp_inr"
    assert "solar_capex_per_mwp_inr" in str(exc_info.value)


def test_all_10_new_keys_exist_and_are_populated_with_sources() -> None:
    """Verify all 10 new keys exist in assumptions.yaml, are populated with cited sources and units."""
    assumptions = load_assumptions()
    expected_new_keys = [
        ("faiman_u0", "assumption", "W/(m2*degC)"),
        ("faiman_u1", "assumption", "W/(m2*degC)/(m/s)"),
        ("dc_ac_ratio", "assumption", "dimensionless"),
        ("capacity_basis", "assumption", "dimensionless"),
        ("ground_albedo", "assumption", "fraction"),
        ("battery_lifetime_years", "assumption", "years"),
        ("battery_replacement_cost_fraction_of_capex", "assumption", "fraction"),
        ("optimizer_objective", "assumption", "dimensionless"),
        ("target_solar_share_default", "assumption", "fraction"),
        ("substation_other_load_mw", "assumption", "MW"),
    ]

    for key, expected_type, expected_unit in expected_new_keys:
        assert key in assumptions, f"Expected key '{key}' missing from assumptions.yaml"
        entry = assumptions[key]
        assert entry.value is not None, f"Expected '{key}' to have non-null value"
        assert len(entry.source) > 0, f"Expected '{key}' to have non-empty source"
        assert entry.unit == expected_unit, f"Expected '{key}' unit '{expected_unit}', got '{entry.unit}'"


def test_allowed_values_rejection_for_new_keys_and_baseline_dispatch() -> None:
    """Verify capacity_basis, optimizer_objective, and baseline_dispatch_rule reject invalid values."""
    # 1. capacity_basis allowed: {mwp_dc, mw_ac}
    for val in ("mwp_dc", "mw_ac"):
        entry = AssumptionEntry(
            value=val,
            unit="dimensionless",
            source="Engineering spec Section 1",
            type="assumption",
            notes="test",
        )
        validate_assumption("capacity_basis", entry, require_populated=True)

    for invalid_val in ("kw_dc", "mw", "invalid_basis"):
        entry = AssumptionEntry(
            value=invalid_val,
            unit="dimensionless",
            source="Engineering spec Section 1",
            type="assumption",
            notes="test",
        )
        with pytest.raises(DataValidationError, match="Invalid value"):
            validate_assumption("capacity_basis", entry, require_populated=True)

    # 2. optimizer_objective allowed: {min_total_annualised_cost, min_annualised_cost_per_kwh_solar_served}
    for val in ("min_total_annualised_cost", "min_annualised_cost_per_kwh_solar_served"):
        entry = AssumptionEntry(
            value=val,
            unit="dimensionless",
            source="Methodology Section 5",
            type="assumption",
            notes="test",
        )
        validate_assumption("optimizer_objective", entry, require_populated=True)

    for invalid_val in ("max_npv", "min_cost", "invalid_obj"):
        entry = AssumptionEntry(
            value=invalid_val,
            unit="dimensionless",
            source="Methodology Section 5",
            type="assumption",
            notes="test",
        )
        with pytest.raises(DataValidationError, match="Invalid value"):
            validate_assumption("optimizer_objective", entry, require_populated=True)

    # 3. baseline_dispatch_rule allowed: {no_battery_fixed_priority}
    valid_dispatch = AssumptionEntry(
        value="no_battery_fixed_priority",
        unit="dimensionless",
        source="Methodology Section 4",
        type="assumption",
        notes="test",
    )
    validate_assumption("baseline_dispatch_rule", valid_dispatch, require_populated=True)

    for invalid_val in ("battery_priority", "greedy_dispatch", "fixed_priority"):
        entry = AssumptionEntry(
            value=invalid_val,
            unit="dimensionless",
            source="Methodology Section 4",
            type="assumption",
            notes="test",
        )
        with pytest.raises(DataValidationError, match="Invalid value"):
            validate_assumption("baseline_dispatch_rule", entry, require_populated=True)


def test_substation_other_load_mw_validation() -> None:
    """Verify substation_other_load_mw: 0 requires 'known limitation' in source."""
    # Non-zero value succeeds with valid source
    entry_nonzero = AssumptionEntry(
        value=1.5,
        unit="MW",
        source="Substation SCADA logs 2024",
        type="sourced",
        notes="test",
    )
    validate_assumption("substation_other_load_mw", entry_nonzero, require_populated=True)

    # 0 succeeds when source contains 'known limitation'
    entry_zero_valid = AssumptionEntry(
        value=0,
        unit="MW",
        source="Feeder metering not segregated; zero non-irrigation load assumed as a known limitation",
        type="sourced",
        notes="test",
    )
    validate_assumption("substation_other_load_mw", entry_zero_valid, require_populated=True)

    # 0 fails when source does not mention 'known limitation'
    entry_zero_invalid = AssumptionEntry(
        value=0,
        unit="MW",
        source="Substation logbook without limitation notice",
        type="sourced",
        notes="test",
    )
    with pytest.raises(DataValidationError, match="known limitation"):
        validate_assumption("substation_other_load_mw", entry_zero_invalid, require_populated=True)

