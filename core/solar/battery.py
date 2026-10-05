"""Battery Energy Storage System (BESS) state and charge/discharge logic.

Enforces PROJECT_SPEC Module 4:
- Battery charge/discharge C-rate limits.
- Round-trip efficiency (symmetric sqrt model for charge and discharge).
- Minimum and maximum State of Charge (SoC).
- Equivalent full cycles (EFC).
"""

from typing import Tuple
import numpy as np

from core.config_loader import ConfigLoader, default_config_loader


class BatterySystem:
    """Manages physical constraints and State of Charge (SoC) tracking for BESS."""

    def __init__(
        self,
        capacity_mwh: float,
        loader: ConfigLoader = default_config_loader,
    ) -> None:
        self.capacity_mwh = max(0.0, capacity_mwh)
        self.capacity_kwh = self.capacity_mwh * 1000.0

        if self.capacity_kwh > 0:
            self.c_rate_charge = float(loader.get_assumption_value("battery_charge_c_rate"))
            self.c_rate_discharge = float(loader.get_assumption_value("battery_discharge_c_rate"))
            self.roundtrip_eff = float(loader.get_assumption_value("battery_roundtrip_efficiency"))
            self.soc_min = float(loader.get_assumption_value("battery_soc_min"))
            self.soc_max = float(loader.get_assumption_value("battery_soc_max"))

            # Symmetric one-way efficiency: sqrt(roundtrip_eff)
            self.eta_oneway = float(np.sqrt(self.roundtrip_eff))

            self.min_energy_kwh = self.capacity_kwh * self.soc_min
            self.max_energy_kwh = self.capacity_kwh * self.soc_max
            self.max_charge_power_kw = self.capacity_kwh * self.c_rate_charge
            self.max_discharge_power_kw = self.capacity_kwh * self.c_rate_discharge

            # Initialize at minimum SoC
            self.current_energy_kwh = self.min_energy_kwh
        else:
            self.c_rate_charge = 0.0
            self.c_rate_discharge = 0.0
            self.roundtrip_eff = 1.0
            self.soc_min = 0.0
            self.soc_max = 0.0
            self.eta_oneway = 1.0
            self.min_energy_kwh = 0.0
            self.max_energy_kwh = 0.0
            self.max_charge_power_kw = 0.0
            self.max_discharge_power_kw = 0.0
            self.current_energy_kwh = 0.0

        self.total_discharge_kwh = 0.0

    def reset(self) -> None:
        """Reset battery state to initial condition."""
        self.current_energy_kwh = self.min_energy_kwh
        self.total_discharge_kwh = 0.0

    def charge(self, available_kwh: float) -> Tuple[float, float]:
        """Charge the battery with available surplus energy (kWh).

        Returns:
        (actual_energy_drawn_from_solar_kwh, thermal_losses_kwh)
        """
        if self.capacity_kwh <= 0 or available_kwh <= 0:
            return 0.0, 0.0

        # Max energy the battery can store before reaching soc_max
        headroom_kwh = self.max_energy_kwh - self.current_energy_kwh
        if headroom_kwh <= 0:
            return 0.0, 0.0

        # Maximum energy input allowed by headroom: headroom / eta_oneway
        max_input_by_capacity = headroom_kwh / self.eta_oneway

        # Limit by power rating (1h interval)
        charge_input_kwh = min(available_kwh, self.max_charge_power_kw, max_input_by_capacity)
        charge_stored_kwh = charge_input_kwh * self.eta_oneway
        losses_kwh = charge_input_kwh - charge_stored_kwh

        self.current_energy_kwh += charge_stored_kwh
        return charge_input_kwh, losses_kwh

    def discharge(self, required_kwh: float) -> Tuple[float, float]:
        """Discharge the battery to serve deficit demand (kWh).

        Returns:
        (energy_delivered_to_demand_kwh, thermal_losses_kwh)
        """
        if self.capacity_kwh <= 0 or required_kwh <= 0:
            return 0.0, 0.0

        # Usable stored energy above soc_min
        available_stored_kwh = self.current_energy_kwh - self.min_energy_kwh
        if available_stored_kwh <= 0:
            return 0.0, 0.0

        # Max delivered energy: stored * eta_oneway
        max_delivered_by_storage = available_stored_kwh * self.eta_oneway

        # Limit by discharge power rating
        delivered_kwh = min(required_kwh, self.max_discharge_power_kw * self.eta_oneway, max_delivered_by_storage)
        stored_withdrawn_kwh = delivered_kwh / self.eta_oneway
        losses_kwh = stored_withdrawn_kwh - delivered_kwh

        self.current_energy_kwh -= stored_withdrawn_kwh
        self.total_discharge_kwh += delivered_kwh

        return delivered_kwh, losses_kwh

    @property
    def equivalent_full_cycles(self) -> float:
        """Calculate equivalent full cycles over the simulation."""
        if self.capacity_kwh <= 0:
            return 0.0
        return self.total_discharge_kwh / self.capacity_kwh
