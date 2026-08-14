"""Constants for the Tuya IR Air Conditioner integration."""

DOMAIN = "tuya_ir_ac"

TUYA_DOMAIN = "tuya"
CONF_AC_DEVICE_ID = "ac_device_id"
CONF_THERMOSTAT_DEVICE_ID = "thermostat_device_id"
DEVICE_CATEGORY = "infrared_ac"

DISCOVERY_COOLDOWN_SECONDS = 60

MODE_TO_TUYA = {
    "cool": 0,
    "heat": 1,
    "auto": 2,
    "fan_only": 3,
    "dry": 4,
}
TUYA_TO_MODE = {value: key for key, value in MODE_TO_TUYA.items()}

FAN_TO_TUYA = {
    "auto": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
}
TUYA_TO_FAN = {value: key for key, value in FAN_TO_TUYA.items()}
