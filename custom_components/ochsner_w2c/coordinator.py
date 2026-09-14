from datetime import timedelta
import logging
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .api import W2CApiError
from .const import OIDS
_LOGGER = logging.getLogger(__name__)
class W2CCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, api, interval, mqtt_enabled=False, mqtt_base_topic='web2com'):
        super().__init__(hass, _LOGGER, name='Ochsner W2C', update_interval=timedelta(seconds=interval))
        self.api, self.mqtt_enabled, self.mqtt_base_topic = api, mqtt_enabled, mqtt_base_topic.rstrip('/')
    async def _async_update_data(self):
        try:
            data = await self.api.read_all(OIDS)
            if self.mqtt_enabled:
                if 'mqtt' not in self.hass.config.components:
                    _LOGGER.warning('MQTT publishing enabled, but Home Assistant MQTT integration is not loaded')
                else:
                    from homeassistant.components import mqtt
                    for oid, value in data.items():
                        await mqtt.async_publish(self.hass, f'{self.mqtt_base_topic}{oid}', str(value), qos=0, retain=True)
            return data
        except W2CApiError as err:
            raise UpdateFailed(str(err)) from err
    async def async_write(self, oid, value):
        await self.api.write_oid(oid, value)
        await self.async_request_refresh()
