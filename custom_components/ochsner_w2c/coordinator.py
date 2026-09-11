from datetime import timedelta
import logging
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator,UpdateFailed
from .api import ApiError
class Coordinator(DataUpdateCoordinator):
 def __init__(self,hass,api,interval):super().__init__(hass,logging.getLogger(__name__),name="Ochsner W2C",update_interval=timedelta(seconds=interval));self.api=api
 async def _async_update_data(self):
  try:return await self.api.read()
  except ApiError as e:raise UpdateFailed(str(e)) from e
 async def write(self,oid,value):await self.api.write(oid,value);await self.async_request_refresh()
