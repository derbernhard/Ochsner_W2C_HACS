from homeassistant.helpers.update_coordinator import CoordinatorEntity
class Entity(CoordinatorEntity):
 _attr_has_entity_name=True
 def __init__(self,c,e,key):super().__init__(c);self._attr_unique_id=f"{e.unique_id}_{key}";self._attr_device_info={'identifiers':{('ochsner_w2c',e.unique_id)},'name':'Ochsner W2C','manufacturer':'Ochsner','model':'W2C'}
