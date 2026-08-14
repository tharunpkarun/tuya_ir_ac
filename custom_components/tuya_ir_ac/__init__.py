"""Tuya IR Air Conditioner integration."""

from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    CONF_AC_DEVICE_ID,
    CONF_THERMOSTAT_DEVICE_ID,
    TUYA_DOMAIN,
)
from .coordinator import TuyaIRThermostatCoordinator

PLATFORMS = [Platform.CLIMATE, Platform.SENSOR]


@dataclass
class TuyaIRRuntimeData:
    """Runtime objects shared by the climate and environmental sensors."""

    manager: Any
    ac_device: Any
    thermostat_device: Any
    coordinator: TuyaIRThermostatCoordinator


def _device_search_text(device: Any) -> str:
    """Return non-sensitive device metadata used for migration matching."""
    return " ".join(
        str(value or "")
        for value in (
            getattr(device, "name", ""),
            getattr(device, "product_name", ""),
            getattr(device, "category", ""),
        )
    ).casefold()


def _resolve_device(
    manager: Any,
    configured_id: str | None,
    required_phrase: str,
) -> Any | None:
    """Resolve a configured device, with a safe migration for the old entry."""
    if configured_id and (device := manager.device_map.get(configured_id)) is not None:
        return device

    candidates = [
        device
        for device in manager.device_map.values()
        if required_phrase in _device_search_text(device)
    ]
    return candidates[0] if len(candidates) == 1 else None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tuya IR control plus the controller's local sensors."""
    tuya_entry = next(
        (
            candidate
            for candidate in hass.config_entries.async_entries(TUYA_DOMAIN)
            if candidate.state is ConfigEntryState.LOADED
            and getattr(candidate, "runtime_data", None) is not None
        ),
        None,
    )
    if tuya_entry is None:
        raise ConfigEntryNotReady("The official Tuya integration is not loaded")

    manager = tuya_entry.runtime_data.manager
    ac_device = _resolve_device(
        manager,
        entry.data.get(CONF_AC_DEVICE_ID),
        "air conditioning",
    )
    thermostat_device = _resolve_device(
        manager,
        entry.data.get(CONF_THERMOSTAT_DEVICE_ID),
        "thermostat",
    )
    if ac_device is None:
        raise ConfigEntryNotReady(
            "The virtual IR air-conditioner device was not found; reconfigure the integration"
        )
    if thermostat_device is None:
        raise ConfigEntryNotReady(
            "The IR thermostat was not found; reconfigure the integration"
        )

    migrated_data = {
        **entry.data,
        CONF_AC_DEVICE_ID: ac_device.id,
        CONF_THERMOSTAT_DEVICE_ID: thermostat_device.id,
    }
    if migrated_data != entry.data:
        hass.config_entries.async_update_entry(entry, data=migrated_data)

    ac_device.set_up = True
    coordinator = TuyaIRThermostatCoordinator(hass, thermostat_device)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = TuyaIRRuntimeData(
        manager=manager,
        ac_device=ac_device,
        thermostat_device=thermostat_device,
        coordinator=coordinator,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
