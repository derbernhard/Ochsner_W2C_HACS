from homeassistant.components.switch import SwitchEntity
from .entity import Entity
async def async_setup_entry(hass,e,add):add([Manual(e.runtime_data,e)])
class Manual(Entity,SwitchEntity):
 _attr_name='Warmwasser manuell';_attr_icon='mdi:water-boiler'
 def __init__(self,c,e):super().__init__(c,e,'water_manual')
 @property
 def is_on(self):
  try:return int(self.coordinator.data.get('/1/2/7/107/0'))==2
  except:return False
 async def async_turn_on(self,**kw):await self.coordinator.write('/1/2/7/107/0',2)
 async def async_turn_off(self,**kw):await self.coordinator.write('/1/2/7/107/0',1)

