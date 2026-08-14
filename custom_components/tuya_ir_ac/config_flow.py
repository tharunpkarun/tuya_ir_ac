"""Config flow for Tuya IR Air Conditioner."""

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_AC_DEVICE_ID,
    CONF_THERMOSTAT_DEVICE_ID,
    DOMAIN,
    TUYA_DOMAIN,
)


class TuyaIRACConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure a Tuya virtual IR AC and its physical thermostat."""

    VERSION = 1

    def _device_choices(self) -> dict[str, str]:
        """Return devices exposed by the loaded official Tuya integration."""
        tuya_entry = next(
            (
                candidate
                for candidate in self.hass.config_entries.async_entries(TUYA_DOMAIN)
                if candidate.state is ConfigEntryState.LOADED
                and getattr(candidate, "runtime_data", None) is not None
            ),
            None,
        )
        if tuya_entry is None:
            return {}

        choices: dict[str, str] = {}
        for device_id, device in tuya_entry.runtime_data.manager.device_map.items():
            name = getattr(device, "name", "") or "Unnamed Tuya device"
            product = getattr(device, "product_name", "") or "Unknown product"
            choices[device_id] = f"{name} — {product} ({device_id[-4:]})"
        return dict(sorted(choices.items(), key=lambda item: item[1].casefold()))

    @staticmethod
    def _suggested_device(choices: dict[str, str], phrase: str) -> str | None:
        """Suggest a device only when its label is unambiguous."""
        matches = [
            device_id
            for device_id, label in choices.items()
            if phrase in label.casefold()
        ]
        return matches[0] if len(matches) == 1 else None

    async def _async_show_device_form(
        self,
        *,
        step_id: str,
        user_input: dict[str, Any] | None,
        defaults: dict[str, str] | None = None,
    ) -> FlowResult:
        """Show and validate the shared device-selection form."""
        choices = self._device_choices()
        if not choices:
            return self.async_abort(reason="tuya_not_ready")

        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input[CONF_AC_DEVICE_ID] == user_input[CONF_THERMOSTAT_DEVICE_ID]:
                errors["base"] = "same_device"
            elif not all(device_id in choices for device_id in user_input.values()):
                errors["base"] = "device_not_found"
            elif step_id == "reconfigure":
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    data_updates=user_input,
                )
            else:
                return self.async_create_entry(title="Tuya IR Air Conditioner", data=user_input)

        defaults = defaults or {}
        ac_default = defaults.get(CONF_AC_DEVICE_ID) or self._suggested_device(
            choices, "air conditioning"
        )
        thermostat_default = defaults.get(
            CONF_THERMOSTAT_DEVICE_ID
        ) or self._suggested_device(choices, "thermostat")

        schema: dict[Any, Any] = {
            vol.Required(
                CONF_AC_DEVICE_ID,
                default=ac_default if ac_default in choices else vol.UNDEFINED,
            ): vol.In(choices),
            vol.Required(
                CONF_THERMOSTAT_DEVICE_ID,
                default=(
                    thermostat_default
                    if thermostat_default in choices
                    else vol.UNDEFINED
                ),
            ): vol.In(choices),
        }
        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema(schema),
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle setup."""
        await self.async_set_unique_id("bedroom_ac_ir")
        self._abort_if_unique_id_configured()
        return await self._async_show_device_form(
            step_id="user",
            user_input=user_input,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Allow changing the paired Tuya devices."""
        entry = self._get_reconfigure_entry()
        return await self._async_show_device_form(
            step_id="reconfigure",
            user_input=user_input,
            defaults=dict(entry.data),
        )
