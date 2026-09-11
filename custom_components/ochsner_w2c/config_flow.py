import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME,CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .api import W2CApi,ApiError
from .const import *
class Flow(config_entries.ConfigFlow,domain=DOMAIN):
 VERSION=1
 async def async_step_user(self,user_input=None):
  errors={}
  if user_input:
   try:await W2CApi(async_get_clientsession(self.hass),user_input[CONF_GATEWAY_HOST],user_input[CONF_TARGET_HOST],user_input[CONF_USERNAME],user_input[CONF_PASSWORD],user_input[CONF_VERIFY_SSL]).read()
   except ApiError:errors['base']='cannot_connect'
   else:
    await self.async_set_unique_id(f"{user_input[CONF_GATEWAY_HOST]}_{user_input[CONF_TARGET_HOST]}");self._abort_if_unique_id_configured();return self.async_create_entry(title=f"Ochsner W2C ({user_input[CONF_TARGET_HOST]})",data=user_input)
  return self.async_show_form(step_id='user',data_schema=vol.Schema({vol.Required(CONF_GATEWAY_HOST,default='192.168.0.10'):str,vol.Required(CONF_TARGET_HOST,default='192.168.0.20'):str,vol.Required(CONF_USERNAME):str,vol.Required(CONF_PASSWORD):str,vol.Required(CONF_VERIFY_SSL,default=False):bool,vol.Optional(CONF_SCAN_INTERVAL,default=60):vol.All(vol.Coerce(int),vol.Range(min=10,max=3600))}),errors=errors)
