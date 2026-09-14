from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from .api import W2CApi
from .const import *
from .coordinator import W2CCoordinator
async def async_setup_entry(hass, entry):
    api = W2CApi(hass, entry.data[CONF_W2C_HOST], entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    coordinator = W2CCoordinator(hass, api, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL), entry.data.get(CONF_MQTT_ENABLED, False), entry.data.get(CONF_MQTT_BASE_TOPIC, DEFAULT_MQTT_BASE_TOPIC))
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True
async def async_unload_entry(hass, entry):
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
