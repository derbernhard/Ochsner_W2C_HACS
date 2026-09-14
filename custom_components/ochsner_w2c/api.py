from homeassistant.components.switch import SwitchEntity
from .entity import W2CEntity
async def async_setup_entry(hass,e,add): add([Manual(e.runtime_data,e)])
class Manual(W2CEntity,SwitchEntity):
    _attr_name='Warmwasser manuell'; _attr_icon='mdi:water-boiler'
    def __init__(self,c,e): super().__init__(c,e,'water_manual')
    @property
    def is_on(self):
        try:return int(self.coordinator.data.get('/1/2/7/107/0'))==2
        except (TypeError,ValueError):return False
    async def async_turn_on(self,**kw): await self.coordinator.async_write('/1/2/7/107/0',2)
    async def async_turn_off(self,**kw): await self.coordinator.async_write('/1/2/7/107/0',1)
