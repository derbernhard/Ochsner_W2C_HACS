"""Data update coordinator for Ochsner W2C."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import W2CApiError
from .const import OIDS

_LOGGER = logging.getLogger(__name__)


class W2CCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, api, interval, mqtt_enabled=False, mqtt_base_topic="web2com"):
        super().__init__(hass, _LOGGER, name="Ochsner W2C", update_interval=timedelta(seconds=interval))
        self.api = api
        self.mqtt_enabled = mqtt_enabled
        self.mqtt_base_topic = mqtt_base_topic.rstrip("/")
        _LOGGER.debug("Coordinator created: interval=%ss mqtt_enabled=%s mqtt_base_topic=%s", interval, mqtt_enabled, self.mqtt_base_topic)

    async def _async_update_data(self):
        _LOGGER.debug("Starting Ochsner W2C coordinator update")
        try:
            data = await self.api.read_all(OIDS)
            if self.mqtt_enabled:
                if "mqtt" not in self.hass.config.components:
                    _LOGGER.warning("MQTT publishing enabled, but Home Assistant MQTT integration is not loaded")
                else:
                    from homeassistant.components import mqtt
                    for oid, value in data.items():
                        await mqtt.async_publish(self.hass, f"{self.mqtt_base_topic}{oid}", str(value), qos=0, retain=True)
                    _LOGGER.debug("Published %s W2C values to MQTT", len(data))
            _LOGGER.debug("Ochsner W2C coordinator update successful: %s values", len(data))
            return data
        except W2CApiError as err:
            _LOGGER.error("Ochsner W2C coordinator update failed: type=%s error=%r", type(err).__name__, err)
            raise UpdateFailed(f"Ochsner W2C update failed: {err}") from err
        except Exception as err:
            _LOGGER.exception("Unexpected error during Ochsner W2C coordinator update")
            raise UpdateFailed(f"Unexpected W2C error: {type(err).__name__}: {err}") from err

    async def async_write(self, oid, value):
        _LOGGER.debug("Coordinator write requested: oid=%s value=%s", oid, value)
        await self.api.write_oid(oid, value)
        await self.async_request_refresh()
