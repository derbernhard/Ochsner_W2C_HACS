"""Number entities for Ochsner W2C."""
from homeassistant.components.number import NumberDeviceClass, NumberEntity
from homeassistant.const import UnitOfTemperature

from .entity import W2CEntity


async def async_setup_entry(hass, entry, add_entities):
    add_entities([
        BoostTarget(entry.runtime_data, entry, "boost_target", "Warmwasser Boost-Ziel"),
    ])


class BoostTarget(W2CEntity, NumberEntity):
    """Zieltemperatur, die der Boost anstrebt. Startet den Boost nicht selbst."""

    _attr_native_step = 0.5
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_device_class = NumberDeviceClass.TEMPERATURE

    def __init__(self, coordinator, entry, key, name):
        super().__init__(coordinator, entry, key)
        self._attr_name = name

    @property
    def native_min_value(self) -> float:
        return self.coordinator.boost_limits[0]

    @property
    def native_max_value(self) -> float:
        return self.coordinator.boost_limits[1]

    @property
    def native_value(self) -> float:
        return self.coordinator.boost_target

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.boost_target = self.coordinator.clamp_target(value)
        self.async_write_ha_state()
