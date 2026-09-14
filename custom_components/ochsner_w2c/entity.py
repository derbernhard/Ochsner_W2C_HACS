from homeassistant.helpers.update_coordinator import CoordinatorEntity
class W2CEntity(CoordinatorEntity):
    _attr_has_entity_name = True
    def __init__(self, coordinator, entry, key):
        super().__init__(coordinator)
        self._attr_unique_id = f'{entry.unique_id}_{key}'
        self._attr_device_info = {'identifiers': {('ochsner_w2c', entry.unique_id)}, 'name': 'Ochsner W2C', 'manufacturer': 'Ochsner', 'model': 'W2C'}
