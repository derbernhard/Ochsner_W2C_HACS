from homeassistant.components.binary_sensor import BinarySensorEntity
from .entity import W2CEntity
async def async_setup_entry(hass,e,add): add([Active(e.runtime_data,e,'heating_active','Heizung aktiv','/1/2/4/107/0',{4,7}),Active(e.runtime_data,e,'hotwater_active','Warmwasser aktiv','/1/2/7/107/0',{1,2,3,4,5})])
class Active(W2CEntity,BinarySensorEntity):
    def __init__(self,c,e,key,name,oid,active): super().__init__(c,e,key); self._attr_name=name; self.oid=oid; self.active=active
    @property
    def is_on(self):
        try:return int(self.coordinator.data.get(self.oid)) in self.active
        except (TypeError,ValueError):return False
