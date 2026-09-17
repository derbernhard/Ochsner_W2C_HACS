import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import W2CApi, W2CApiError
from .const import *


class OchsnerW2CConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input:
            try:
                session = async_get_clientsession(self.hass)
                await W2CApi(
                    session,
                    user_input[CONF_W2C_HOST],
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                ).read_oid(OIDS[0])
            except (W2CApiError, OSError, TimeoutError):
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(user_input[CONF_W2C_HOST].lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Ochsner W2C ({user_input[CONF_W2C_HOST]})",
                    data=user_input,
                )

        schema = vol.Schema({
            vol.Required(CONF_W2C_HOST, default="192.168.0.20"): str,
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
                vol.Coerce(int), vol.Range(min=10, max=3600)
            ),
            vol.Optional(CONF_MQTT_ENABLED, default=False): bool,
            vol.Optional(CONF_MQTT_BASE_TOPIC, default=DEFAULT_MQTT_BASE_TOPIC): str,
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
