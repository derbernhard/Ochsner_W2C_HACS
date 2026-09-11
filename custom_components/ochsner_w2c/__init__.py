from homeassistant.const import CONF_USERNAME,CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .api import W2CApi
from .coordinator import Coordinator
from .const import *
async def async_setup_entry(hass,entry):
 c=Coordinator(hass,W2CApi(async_get_clientsession(hass),entry.data[CONF_GATEWAY_HOST],entry.data[CONF_TARGET_HOST],entry.data[CONF_USERNAME],entry.data[CONF_PASSWORD],entry.data.get(CONF_VERIFY_SSL,False)),entry.data.get(CONF_SCAN_INTERVAL,DEFAULT_SCAN_INTERVAL));await c.async_config_entry_first_refresh();entry.runtime_data=c;await hass.config_entries.async_forward_entry_setups(entry,PLATFORMS);return True
async def async_unload_entry(hass,entry):return await hass.config_entries.async_unload_platforms(entry,PLATFORMS)
