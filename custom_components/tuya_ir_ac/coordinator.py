"""Local environmental readings from the physical Tuya IR thermostat."""

from __future__ import annotations

from datetime import timedelta
from time import monotonic
from typing import Any

import tinytuya

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DISCOVERY_COOLDOWN_SECONDS, DOMAIN


class TuyaIRThermostatCoordinator(DataUpdateCoordinator[dict[str, float]]):
    """Poll the controller locally because Tuya Sharing omits its sensor schema."""

    def __init__(self, hass: HomeAssistant, device: Any) -> None:
        super().__init__(
            hass,
            logger=__import__("logging").getLogger(__name__),
            name=f"{DOMAIN} room conditions",
            update_interval=timedelta(seconds=30),
            always_update=False,
        )
        self.device = device
        self._host: str | None = None
        self._last_discovery_attempt = 0.0

    def _discover_host(self, *, force: bool = False) -> str | None:
        """Discover the thermostat IP by matching its stable Tuya device ID."""
        now = monotonic()
        if self._host is not None and not force:
            return self._host
        if now - self._last_discovery_attempt < DISCOVERY_COOLDOWN_SECONDS:
            return self._host

        self._last_discovery_attempt = now
        devices = tinytuya.deviceScan(
            verbose=False,
            color=False,
            poll=False,
            byID=True,
        )
        info = devices.get(self.device.id)
        if not isinstance(info, dict):
            info = next(
                (
                    candidate
                    for candidate in devices.values()
                    if isinstance(candidate, dict)
                    and (candidate.get("gwId") or candidate.get("id"))
                    == self.device.id
                ),
                None,
            )
        if isinstance(info, dict) and info.get("ip"):
            self._host = str(info["ip"])
        return self._host

    @staticmethod
    def _extract_dps(result: Any) -> dict[Any, Any] | None:
        """Extract datapoints from the response formats used by TinyTuya."""
        dps = result.get("dps") if isinstance(result, dict) else None
        if not isinstance(dps, dict) and isinstance(result, dict):
            data = result.get("data")
            dps = data.get("dps") if isinstance(data, dict) else None
        return dps if isinstance(dps, dict) else None

    def _status(self, host: str, local_key: str) -> Any:
        """Read one local status response and close the socket afterward."""
        local = tinytuya.Device(
            self.device.id,
            host,
            local_key,
            version=3.3,
            persist=False,
            connection_timeout=3,
            connection_retry_limit=1,
        )
        try:
            return local.status()
        finally:
            if hasattr(local, "close"):
                local.close()

    def _read_local(self) -> dict[str, float]:
        local_key = getattr(self.device, "local_key", "") or ""
        if len(local_key) != 16:
            raise UpdateFailed("The thermostat local key is unavailable")

        host = self._discover_host()
        if host is None:
            raise UpdateFailed("The thermostat was not found by Tuya UDP discovery")

        result = self._status(host, local_key)
        dps = self._extract_dps(result)
        if not isinstance(dps, dict):
            previous_host = host
            discovered_host = self._discover_host(force=True)
            if discovered_host and discovered_host != previous_host:
                result = self._status(discovered_host, local_key)
                dps = self._extract_dps(result)
        if not isinstance(dps, dict):
            raise UpdateFailed(f"Thermostat returned no datapoints: {result}")

        def value(dp_id: int) -> Any:
            return dps.get(dp_id, dps.get(str(dp_id)))

        try:
            temperature = float(value(2)) / 10
            humidity = float(value(12))
        except (TypeError, ValueError) as err:
            raise UpdateFailed("Temperature or humidity datapoint is missing") from err

        if not -20 <= temperature <= 80:
            raise UpdateFailed(f"Invalid room temperature: {temperature}")
        if not 0 <= humidity <= 100:
            raise UpdateFailed(f"Invalid room humidity: {humidity}")
        return {"temperature": round(temperature, 1), "humidity": round(humidity, 1)}

    async def _async_update_data(self) -> dict[str, float]:
        try:
            return await self.hass.async_add_executor_job(self._read_local)
        except UpdateFailed:
            raise
        except Exception as err:
            raise UpdateFailed(f"Unable to read the IR thermostat: {err}") from err
