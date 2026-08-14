"""Room temperature and humidity sensors for the Tuya IR thermostat."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import TUYA_DOMAIN
from .coordinator import TuyaIRThermostatCoordinator


@dataclass(frozen=True, kw_only=True)
class TuyaIRSensorDescription(SensorEntityDescription):
    """Describe one environmental datapoint."""

    data_key: str


SENSORS = (
    TuyaIRSensorDescription(
        key="room_temperature",
        data_key="temperature",
        name="Room temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    TuyaIRSensorDescription(
        key="room_humidity",
        data_key="humidity",
        name="Room humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the controller's environmental sensors."""
    runtime = entry.runtime_data
    async_add_entities(
        [
            TuyaIREnvironmentSensor(
                runtime.coordinator, runtime.thermostat_device, description
            )
            for description in SENSORS
        ]
    )


class TuyaIREnvironmentSensor(
    CoordinatorEntity[TuyaIRThermostatCoordinator], SensorEntity
):
    """Expose a locally measured room condition."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, device, description) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"tuya_ir_thermostat.{device.id}.{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(TUYA_DOMAIN, device.id)},
            manufacturer="Tuya",
            model=device.product_name,
            name=device.name,
        )

    @property
    def native_value(self) -> float | None:
        """Return the latest local reading."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self.entity_description.data_key)
