from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import W2CApi
from .const import *
from .coordinator import W2CCoordinator

async def async_migrate_entry(hass, entry: ConfigEntry) -> bool:
    if entry.version == 1:
        data = dict(entry.data)
        if "w2c_host" not in data:
            data["w2c_host"] = data.get("target_host", "192.168.0.20")
        data.pop("gateway_host", None)
        data.pop("target_host", None)
        hass.config_entries.async_update_entry(
            entry,
            data=data,
            version=2,
        )
    return True

async def async_setup_entry(hass, entry):
    api = W2CApi(async_get_clientsession(hass), entry.data[CONF_W2C_HOST], entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    coordinator = W2CCoordinator(hass, api, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL), entry.data.get(CONF_MQTT_ENABLED, False), entry.data.get(CONF_MQTT_BASE_TOPIC, DEFAULT_MQTT_BASE_TOPIC))
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True
async def async_unload_entry(hass, entry):
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
