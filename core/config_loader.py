"""Configuration loader for assumptions and feasibility rules.

Enforces PROJECT_SPEC Section 0 Rule 2:
'Every physical, financial or policy constant lives in config/assumptions.yaml or config/rules.yaml.
 Each entry has: value, unit, source (document + section, or URL), type (sourced or assumption), notes.
 If a needed entry has an empty value or source, raise MissingInputError naming the exact key.
 Never fill these in yourself. Create the templates with empty fields and list them for me.'
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
import yaml

from core.errors import MissingInputError, DataValidationError

logger = logging.getLogger(__name__)

ALLOWED_ASSUMPTION_TYPES: set[str] = {"sourced", "assumption"}

ALLOWED_STRING_VALUES: Dict[str, set[str]] = {
    "nasa_hour_convention": {"hour_beginning", "centred", "hour_ending"},
    "interval_convention_open_meteo": {"preceding_hour", "following_hour"},
    "effective_rainfall_method": {"usda_scs", "fao_56_dependable"},
    "capacity_basis": {"mwp_dc", "mw_ac"},
    "optimizer_objective": {
        "min_total_annualised_cost",
        "min_annualised_cost_per_kwh_solar_served",
    },
    "baseline_dispatch_rule": {"no_battery_fixed_priority"},
}
ALLOWED_VALUES: Dict[str, set[str]] = ALLOWED_STRING_VALUES

STAGE_ASSUMPTIONS: Dict[str, List[str]] = {
    "stage_1": [],
    "stage_2": [
        "interval_convention_open_meteo",
        "nasa_hour_convention",
        "crop_area_unit",
        "latur_annual_rainfall_reference_min_mm",
        "latur_annual_rainfall_reference_max_mm",
        "expected_annual_ghi_min_kwh_per_m2",
        "expected_annual_ghi_max_kwh_per_m2",
        "expected_annual_et0_min_mm",
        "expected_annual_et0_max_mm",
    ],
    "stage_3": [
        "effective_rainfall_method",
        "irrigation_efficiency_drip",
        "irrigation_efficiency_sprinkler",
        "irrigation_efficiency_surface",
        "groundwater_depth_m",
        "drawdown_m",
        "friction_head_m",
        "pump_efficiency",
        "motor_efficiency",
    ],
    "stage_4": [
        "pv_tilt_deg",
        "pv_azimuth_deg",
        "transposition_model",
        "cell_temperature_model",
        "faiman_u0",
        "faiman_u1",
        "wind_speed_measurement_height_m",
        "pv_temp_coeff_pmax",
        "dc_losses_fraction",
        "inverter_efficiency",
        "soiling_loss_fraction",
        "availability_loss_fraction",
        "annual_degradation_rate",
        "expected_specific_yield_min_kwh_per_kwp",
        "expected_specific_yield_max_kwh_per_kwp",
        "expected_cuf_min_percent",
        "expected_cuf_max_percent",
        "dc_ac_ratio",
        "capacity_basis",
        "ground_albedo",
        "battery_charge_c_rate",
        "battery_discharge_c_rate",
        "battery_roundtrip_efficiency",
        "battery_soc_min",
        "battery_soc_max",
        "transformer_power_factor",
        "transformer_max_loading_fraction",
        "baseline_dispatch_rule",
        "energy_balance_tolerance_kwh",
        "substation_other_load_mw",
    ],
    "stage_5": [
        "solar_capex_per_mwp",
        "solar_capex_per_mwp_inr",
        "solar_om_fraction_of_capex",
        "solar_om_per_mwp_per_year_inr",
        "battery_capex_per_mwh",
        "battery_capex_per_mwh_inr",
        "battery_om_fraction_of_capex",
        "battery_om_per_mwh_per_year_inr",
        "discount_rate",
        "project_lifetime_years",
        "grid_tariff_per_kwh",
        "agricultural_electricity_tariff_inr_per_kwh",
        "optimizer_solar_capacity_min_mwp",
        "optimizer_solar_capacity_max_mwp",
        "optimizer_solar_capacity_step_mwp",
        "optimizer_battery_capacity_min_mwh",
        "optimizer_battery_capacity_max_mwh",
        "optimizer_battery_capacity_step_mwh",
        "grid_emission_factor_kg_co2_per_kwh",
        "battery_lifetime_years",
        "battery_replacement_cost_fraction_of_capex",
        "optimizer_objective",
        "target_solar_share_default",
    ],
    "stage_6": [
        "land_requirement_acres_per_mw",
        "land_cost_per_acre",
        "line_capex_per_km_11kv",
        "line_capex_per_km_33kv",
        "substation_bay_cost",
    ],
    "stage_7": [],
}

STAGE_ALIASES: Dict[str, str] = {
    "1": "stage_1",
    "stage1": "stage_1",
    "stage_1": "stage_1",
    "skeleton": "stage_1",
    "2": "stage_2",
    "stage2": "stage_2",
    "stage_2": "stage_2",
    "data": "stage_2",
    "3": "stage_3",
    "stage3": "stage_3",
    "stage_3": "stage_3",
    "demand": "stage_3",
    "irrigation": "stage_3",
    "4": "stage_4",
    "stage4": "stage_4",
    "stage_4": "stage_4",
    "solar": "stage_4",
    "battery": "stage_4",
    "dispatch": "stage_4",
    "5": "stage_5",
    "stage5": "stage_5",
    "stage_5": "stage_5",
    "optimizer": "stage_5",
    "economics": "stage_5",
    "emissions": "stage_5",
    "6": "stage_6",
    "stage6": "stage_6",
    "stage_6": "stage_6",
    "feasibility": "stage_6",
    "rules": "stage_6",
    "7": "stage_7",
    "stage7": "stage_7",
    "stage_7": "stage_7",
    "app": "stage_7",
    "summary": "stage_7",
}


def get_project_root() -> Path:
    """Return the absolute Path to the project root directory."""
    return Path(__file__).resolve().parent.parent


class AssumptionEntry(BaseModel):
    """Pydantic model representing a single assumption entry."""

    model_config = ConfigDict(extra="forbid")

    value: Optional[Any] = None
    unit: str = Field(..., description="Measurement unit of the parameter")
    source: Optional[str] = Field(default="", description="Citation of document + section or URL")
    type: str = Field(..., description="Classification: must be exactly 'sourced' or 'assumption'")
    notes: str = Field(default="", description="Context, interpretation, or notes")

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in ALLOWED_ASSUMPTION_TYPES:
            raise ValueError(f"type must be exactly 'sourced' or 'assumption', got '{v}'")
        return v

    def is_populated(self) -> bool:
        """Check if both value and source are populated and type is valid."""
        if self.value is None:
            return False
        if not self.source or not str(self.source).strip():
            return False
        if self.type not in ALLOWED_ASSUMPTION_TYPES:
            return False
        return True


class RuleEntry(BaseModel):
    """Pydantic model representing a feasibility screening rule."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="Unique rule identifier")
    description: str = Field(..., description="Plain-language description of the rule")
    parameter: str = Field(..., description="Evaluated variable name")
    operator: str = Field(..., description="Comparison operator (e.g. <=, >=, ==)")
    threshold: Optional[Any] = Field(default=None, description="Rule threshold limit")
    unit: str = Field(..., description="Unit of parameter and threshold")
    source: Optional[str] = Field(default="", description="Originating regulation or document section")
    severity: Literal["blocking", "warning"] = Field(..., description="Failure severity")
    notes: str = Field(default="", description="Engineering notes or context")

    def is_populated(self) -> bool:
        """Check if both threshold and source are populated."""
        if self.threshold is None:
            return False
        if not self.source or not str(self.source).strip():
            return False
        return True


class ConfigLoader:
    """Loads and validates configuration from assumptions.yaml and rules.yaml."""

    def __init__(self, root_dir: Optional[Path] = None) -> None:
        self.root_dir: Path = root_dir or get_project_root()
        self.assumptions_path: Path = self.root_dir / "config" / "assumptions.yaml"
        self.rules_path: Path = self.root_dir / "config" / "rules.yaml"

    def validate_assumption(
        self, key: str, entry: AssumptionEntry, require_populated: bool = True
    ) -> None:
        """Validate an assumption entry against domain rules.

        Enforces:
        1. type must be exactly 'sourced' or 'assumption'.
        2. if type is 'sourced' and source is empty, raise MissingInputError naming the key.
        3. if type is 'assumption', still require a non-empty source (used as written justification).
        4. string-valued keys must be in their allowed lists:
           - nasa_hour_convention in {hour_beginning, centred, hour_ending}
           - interval_convention_open_meteo in {preceding_hour, following_hour}
           - effective_rainfall_method in {usda_scs, fao_56_dependable}
        """
        if entry.type not in ALLOWED_ASSUMPTION_TYPES:
            raise DataValidationError(
                f"Assumption '{key}' has invalid type '{entry.type}'. "
                f"Must be exactly 'sourced' or 'assumption'."
            )

        if require_populated and entry.value is None:
            raise MissingInputError(
                key,
                f"Assumption '{key}' has empty value in assumptions.yaml. Fill this in before continuing.",
            )

        if require_populated or entry.value is not None:
            if not entry.source or not str(entry.source).strip():
                if entry.type == "sourced":
                    raise MissingInputError(
                        key,
                        f"Assumption '{key}' of type 'sourced' has empty source. A document citation or reference is required.",
                    )
                else:  # assumption
                    raise MissingInputError(
                        key,
                        f"Assumption '{key}' of type 'assumption' has empty source. A written justification is required as source.",
                    )

        if entry.value is not None and key in ALLOWED_STRING_VALUES:
            if entry.value not in ALLOWED_STRING_VALUES[key]:
                raise DataValidationError(
                    f"Invalid value '{entry.value}' for '{key}'. "
                    f"Must be one of {sorted(ALLOWED_STRING_VALUES[key])}."
                )

        if entry.value is not None and key == "substation_other_load_mw":
            if entry.value == 0:
                source_text = str(entry.source or "").lower()
                if "known limitation" not in source_text:
                    raise DataValidationError(
                        f"Assumption '{key}' has a value of 0, which is allowed only if the source "
                        f"field states that this is a known limitation."
                    )

    def load_raw_assumptions(self) -> Dict[str, AssumptionEntry]:
        """Load all assumption entries from YAML without requiring values/sources to be populated."""
        if not self.assumptions_path.exists():
            raise MissingInputError(
                "assumptions.yaml",
                f"Assumptions config file not found at {self.assumptions_path}",
            )

        with open(self.assumptions_path, "r", encoding="utf-8") as f:
            raw_data = yaml.safe_load(f)

        if not isinstance(raw_data, dict):
            raise MissingInputError(
                "assumptions.yaml",
                f"Assumptions YAML at {self.assumptions_path} must be a dictionary",
            )

        assumptions: Dict[str, AssumptionEntry] = {}
        for key, entry_dict in raw_data.items():
            if not isinstance(entry_dict, dict):
                raise DataValidationError(f"Invalid format for assumption '{key}': expected dictionary")

            entry_type = entry_dict.get("type")
            if entry_type not in ALLOWED_ASSUMPTION_TYPES:
                raise DataValidationError(
                    f"Assumption '{key}' has invalid type '{entry_type}'. Must be exactly 'sourced' or 'assumption'."
                )

            try:
                entry = AssumptionEntry(**entry_dict)
            except Exception as e:
                raise DataValidationError(f"Validation error for assumption '{key}': {e}") from e

            # Validation is lazy: performed when requested or in validate_for_stage

            assumptions[key] = entry
        return assumptions

    def get_assumption(self, key: str, require_populated: bool = True) -> AssumptionEntry:
        """Retrieve a specific assumption by key.

        If require_populated is True and either value or source is empty,
        raises MissingInputError naming the exact key.
        """
        assumptions = self.load_raw_assumptions()
        if key not in assumptions:
            raise MissingInputError(
                key,
                f"Configuration key '{key}' was not found in {self.assumptions_path}",
            )

        entry = assumptions[key]
        self.validate_assumption(key, entry, require_populated=require_populated)
        return entry

    def get_assumption_value(self, key: str) -> Any:
        """Retrieve the validated value of an assumption key."""
        entry = self.get_assumption(key, require_populated=True)
        return entry.value

    def get_unpopulated_assumptions(self) -> List[str]:
        """Return a list of assumption keys that currently have null value or empty source."""
        assumptions = self.load_raw_assumptions()
        return [k for k, v in assumptions.items() if not v.is_populated()]

    def load_raw_rules(self) -> List[RuleEntry]:
        """Load all rules from rules.yaml without requiring thresholds to be populated."""
        if not self.rules_path.exists():
            raise MissingInputError(
                "rules.yaml",
                f"Rules config file not found at {self.rules_path}",
            )

        with open(self.rules_path, "r", encoding="utf-8") as f:
            raw_data = yaml.safe_load(f)

        if not isinstance(raw_data, dict) or "rules" not in raw_data:
            raise MissingInputError(
                "rules.yaml",
                f"Rules YAML at {self.rules_path} must contain a top-level 'rules' list",
            )

        return [RuleEntry(**item) for item in raw_data["rules"]]

    def get_rule(self, rule_id: str, require_populated: bool = True) -> RuleEntry:
        """Retrieve a rule by id.

        If require_populated is True and threshold or source is empty,
        raises MissingInputError naming the rule id.
        """
        rules = self.load_raw_rules()
        for rule in rules:
            if rule.id == rule_id:
                if require_populated and not rule.is_populated():
                    raise MissingInputError(
                        rule_id,
                        f"Feasibility rule '{rule_id}' has empty threshold or source in rules.yaml. "
                        f"(threshold: {rule.threshold}, source: '{rule.source}'). Fill this in before continuing.",
                    )
                return rule

        raise MissingInputError(
            rule_id,
            f"Rule '{rule_id}' was not found in {self.rules_path}",
        )

    def get_unpopulated_rules(self) -> List[str]:
        """Return a list of rule IDs that currently have null threshold or empty source."""
        rules = self.load_raw_rules()
        return [r.id for r in rules if not r.is_populated()]

    def validate_for_stage(self, stage_name: str | int) -> None:
        """Validate all assumption entries required for a given project stage.

        Keys belonging to other/unrelated stages are not checked, ensuring that
        unpopulated keys for later stages do not cause premature validation failures.
        """
        key_norm = str(stage_name).strip().lower()
        stage_key = STAGE_ALIASES.get(key_norm, key_norm)
        if stage_key not in STAGE_ASSUMPTIONS:
            raise DataValidationError(
                f"Unknown stage '{stage_name}'. Known stages: {sorted(STAGE_ASSUMPTIONS.keys())}"
            )

        required_keys = STAGE_ASSUMPTIONS[stage_key]
        for key in required_keys:
            self.get_assumption(key, require_populated=True)


# Convenience singleton loader
default_config_loader = ConfigLoader()


def load_assumptions(config_path: Optional[Path] = None) -> Dict[str, AssumptionEntry]:
    """Helper to load all assumptions."""
    loader = ConfigLoader(root_dir=config_path) if config_path else default_config_loader
    return loader.load_raw_assumptions()


def get_assumption(key: str, require_populated: bool = True) -> AssumptionEntry:
    """Helper to get an assumption entry."""
    return default_config_loader.get_assumption(key, require_populated=require_populated)


def get_assumption_value(key: str) -> Any:
    """Helper to get an assumption value."""
    return default_config_loader.get_assumption_value(key)


def validate_assumption(
    key: str, entry: AssumptionEntry, require_populated: bool = True
) -> None:
    """Helper to validate an assumption entry."""
    default_config_loader.validate_assumption(key, entry, require_populated=require_populated)


def load_rules(config_path: Optional[Path] = None) -> List[RuleEntry]:
    """Helper to load all rules."""
    loader = ConfigLoader(root_dir=config_path) if config_path else default_config_loader
    return loader.load_raw_rules()


def get_rule(rule_id: str, require_populated: bool = True) -> RuleEntry:
    """Helper to get a rule entry."""
    return default_config_loader.get_rule(rule_id, require_populated=require_populated)


def validate_for_stage(stage_name: str | int, config_path: Optional[Path] = None) -> None:
    """Helper to validate assumptions for a given stage."""
    loader = ConfigLoader(root_dir=config_path) if config_path else default_config_loader
    loader.validate_for_stage(stage_name)
