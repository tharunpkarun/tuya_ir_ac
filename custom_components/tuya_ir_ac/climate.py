"""Climate entity for a Tuya virtual infrared air conditioner."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from homeassistant.components.tuya.const import TUYA_HA_SIGNAL_UPDATE_ENTITY

from .const import (
    DEVICE_CATEGORY,
    FAN_TO_TUYA,
    MODE_TO_TUYA,
    TUYA_DOMAIN,
    TUYA_TO_FAN,
    TUYA_TO_MODE,
)

HVAC_MODES = [
    HVACMode.OFF,
    HVACMode.COOL,
    HVACMode.HEAT,
    HVACMode.AUTO,
    HVACMode.FAN_ONLY,
    HVACMode.DRY,
]
FAN_MODES = ["auto", "low", "medium", "high"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Bedroom AC entity."""
    runtime = entry.runtime_data
    async_add_entities(
        [TuyaIRClimate(runtime.ac_device, runtime.manager, runtime.coordinator)]
    )
    await hass.async_add_executor_job(runtime.manager.refresh_mq)


class TuyaIRClimate(ClimateEntity, RestoreEntity):
    """Optimistic Climate entity for the stateless Tuya IR remote."""

    _attr_assumed_state = True
    _attr_fan_modes = FAN_MODES
    _attr_has_entity_name = True
    _attr_hvac_modes = HVAC_MODES
    _attr_max_temp = 30
    _attr_min_temp = 16
    _attr_name = None
    _attr_precision = 0.1
    _attr_should_poll = False
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_target_temperature_step = 1.0
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, device: Any, manager: Any, coordinator: Any) -> None:
        """Initialize the entity with safe default IR state."""
        self.device = device
        self.manager = manager
        self.coordinator = coordinator
        self._attr_unique_id = f"tuya_ir_ac.{device.id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(TUYA_DOMAIN, device.id)},
            manufacturer="Tuya",
            model=device.product_name,
            name=device.name,
        )
        # Seed from the last Homebridge-cached Tuya IR state. This is only used
        # for the one-time migration; subsequent restarts use RestoreEntity.
        self._is_on = True
        self._last_mode = HVACMode.COOL
        self._target_temperature = 25.0
        self._fan_mode = "auto"

    @property
    def available(self) -> bool:
        """Return cloud availability."""
        return bool(self.device.online)

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the optimistic HVAC mode."""
        return self._last_mode if self._is_on else HVACMode.OFF

    @property
    def target_temperature(self) -> float:
        """Return the last commanded target temperature."""
        return self._target_temperature

    @property
    def current_temperature(self) -> float | None:
        """Return the room temperature measured by the physical controller."""
        return self.coordinator.data.get("temperature") if self.coordinator.data else None

    @property
    def fan_mode(self) -> str:
        """Return the last commanded fan mode."""
        return self._fan_mode

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Persist optimistic details used after a restart."""
        return {
            "ir_state_assumed": True,
            "current_humidity": (
                self.coordinator.data.get("humidity") if self.coordinator.data else None
            ),
            "last_hvac_mode": self._last_mode,
            "schema_version": 2,
            "tuya_category": DEVICE_CATEGORY,
        }

    async def async_added_to_hass(self) -> None:
        """Restore the last command and subscribe to Tuya updates."""
        await super().async_added_to_hass()
        if (
            (last_state := await self.async_get_last_state()) is not None
            and last_state.attributes.get("schema_version") == 2
        ):
            if last_state.state in MODE_TO_TUYA:
                self._last_mode = HVACMode(last_state.state)
                self._is_on = True
            elif last_state.state == HVACMode.OFF:
                self._is_on = False
                restored_mode = last_state.attributes.get("last_hvac_mode")
                if restored_mode in MODE_TO_TUYA:
                    self._last_mode = HVACMode(restored_mode)

            if (temperature := last_state.attributes.get(ATTR_TEMPERATURE)) is not None:
                self._target_temperature = self._normalize_temperature(temperature)
            if (fan_mode := last_state.attributes.get(ATTR_FAN_MODE)) in FAN_TO_TUYA:
                self._fan_mode = fan_mode

        self._apply_reported_status()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{TUYA_HA_SIGNAL_UPDATE_ENTITY}_{self.device.id}",
                self._handle_tuya_update,
            )
        )
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_sensor_update)
        )

    @callback
    def _handle_sensor_update(self) -> None:
        """Refresh the climate card when local room conditions change."""
        self.async_write_ha_state()

    @callback
    def _handle_tuya_update(
        self,
        updated_status_properties: list[str] | None,
        dp_timestamps: dict[str, int] | None,
    ) -> None:
        """Use any future state reports while remaining optimistic."""
        self._apply_reported_status()
        self.async_write_ha_state()

    def _apply_reported_status(self) -> None:
        """Apply Tuya's optional virtual-remote state fields."""
        status = self.device.status
        if "power" in status:
            value = status["power"]
            self._is_on = value is True or str(value).lower() in {"1", "true", "on"}
        if "mode" in status:
            try:
                mode = TUYA_TO_MODE.get(int(status["mode"]))
                if mode is not None:
                    self._last_mode = HVACMode(mode)
            except (TypeError, ValueError):
                pass
        if "temp" in status:
            self._target_temperature = self._normalize_temperature(status["temp"])
        if "wind" in status:
            try:
                fan_mode = TUYA_TO_FAN.get(int(status["wind"]))
                if fan_mode is not None:
                    self._fan_mode = fan_mode
            except (TypeError, ValueError):
                pass

    @staticmethod
    def _normalize_temperature(value: Any) -> float:
        """Clamp the IR temperature to the verified 16–30 °C range."""
        return float(max(16, min(30, round(float(value)))))

    def _power_on_commands(self) -> list[dict[str, Any]]:
        """Build a complete IR state for a deterministic power-on command."""
        return [
            {"code": "PowerOn", "value": "PowerOn"},
            {"code": "M", "value": MODE_TO_TUYA[self._last_mode]},
            {"code": "T", "value": int(self._target_temperature)},
            {"code": "F", "value": FAN_TO_TUYA[self._fan_mode]},
        ]

    async def _async_send(self, commands: list[dict[str, Any]]) -> None:
        """Send verified virtual-remote commands through Tuya Sharing."""
        await self.hass.async_add_executor_job(
            self.manager.send_commands, self.device.id, commands
        )

    async def async_turn_on(self) -> None:
        """Turn on with the complete restored IR state."""
        await self._async_send(self._power_on_commands())
        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Turn off the air conditioner."""
        await self._async_send([{"code": "PowerOff", "value": "PowerOff"}])
        self._is_on = False
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the verified Tuya IR operating mode."""
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
            return
        if hvac_mode.value not in MODE_TO_TUYA:
            return

        was_off = not self._is_on
        self._last_mode = hvac_mode
        if was_off:
            await self._async_send(self._power_on_commands())
        else:
            await self._async_send(
                [{"code": "M", "value": MODE_TO_TUYA[hvac_mode]}]
            )
        self._is_on = True
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set a target temperature, sending it immediately only when on."""
        if ATTR_TEMPERATURE not in kwargs:
            return
        self._target_temperature = self._normalize_temperature(
            kwargs[ATTR_TEMPERATURE]
        )
        if self._is_on:
            await self._async_send(
                [{"code": "T", "value": int(self._target_temperature)}]
            )
        self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set a fan speed, sending it immediately only when on."""
        if fan_mode not in FAN_TO_TUYA:
            return
        self._fan_mode = fan_mode
        if self._is_on:
            await self._async_send(
                [{"code": "F", "value": FAN_TO_TUYA[fan_mode]}]
            )
        self.async_write_ha_state()
