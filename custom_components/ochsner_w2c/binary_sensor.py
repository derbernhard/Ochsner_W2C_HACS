from homeassistant.components.binary_sensor import BinarySensorEntity

from .entity import W2CEntity


async def async_setup_entry(hass, entry, add_entities):
    add_entities([
        Active(entry.runtime_data, entry, "heating_active", "Heizung aktiv", "/1/2/4/107/0", {4, 7}),
        Active(entry.runtime_data, entry, "hotwater_active", "Warmwasser aktiv", "/1/2/7/107/0", {1, 2, 3, 4, 5}),
        BoostRunning(entry.runtime_data, entry),
    ])


class Active(W2CEntity, BinarySensorEntity):
    def __init__(self, c, e, key, name, oid, active):
        super().__init__(c, e, key)
        self._attr_name = name
        self.oid = oid
        self.active = active

    @property
    def is_on(self):
        try:
            return int(self.coordinator.data.get(self.oid)) in self.active
        except (TypeError, ValueError):
            return False


class BoostRunning(W2CEntity, BinarySensorEntity):
    """Zeigt an, ob der Warmwasser-Boost gerade läuft."""

    _attr_name = "Warmwasser Boost aktiv"
    _attr_icon = "mdi:water-boiler-alert"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "ww_boost_running")

    @property
    def is_on(self) -> bool:
        return self.coordinator.boost_active
