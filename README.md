# Tuya IR Air Conditioner

A Home Assistant custom integration for controlling a Tuya virtual infrared air conditioner while reading room temperature and humidity directly from its physical Tuya thermostat.

The integration uses the official Home Assistant Tuya integration for IR commands and TinyTuya for local sensor polling. It discovers the thermostat by its stable Tuya device ID, so DHCP address changes do not require manual reconfiguration.

## Features

- Climate entity with heating, cooling, automatic, dry, and fan-only modes
- Reliable power-on: Tuya IR commands are sent one at a time with one retry for
  Tuya cloud error 1109
- Optimistic restoration of the last successfully commanded mode, temperature,
  and fan speed
- A temperature change while off starts the AC in Cool mode
- HA keeps the assumed IR state from its own commands; Tuya virtual-remote
  status is not treated as physical AC feedback
- Local temperature and humidity sensors
- Automatic Tuya UDP IP rediscovery after a network error
- Config-flow device selection without hard-coded device IDs or IP addresses

## Requirements

- Home Assistant 2026.7 or newer
- The official Tuya integration configured and loaded
- Home Assistant and the physical thermostat on the same broadcast network
- UDP ports 6666, 6667, and 7000 available for Tuya discovery
- Local TCP access from Home Assistant to the thermostat

## Installation with HACS

1. Open HACS and add `https://github.com/tharunpkarun/tuya_ir_ac` as a custom integration repository.
2. Install **Tuya IR Air Conditioner**.
3. Restart Home Assistant.
4. Add the integration and select the virtual IR air conditioner and physical thermostat.

## Author

Created and maintained by **Tharun P Karun**.

## License

MIT
