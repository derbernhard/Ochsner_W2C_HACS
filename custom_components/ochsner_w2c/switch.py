"""Switch entities for Ochsner W2C."""
from homeassistant.components.switch import SwitchEntity

from .const import OID_WW_ACTUAL
from .entity import W2CEntity


async def async_setup_entry(hass, entry, add_entities):
    add_entities([
        Boost(entry.runtime_data, entry),
    ])


class Boost(W2CEntity, SwitchEntity):
    """Aktiviert den Warmwasser-Boost."""

    _attr_name = "Warmwasser Boost"
    _attr_icon = "mdi:water-boiler"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "ww_boost")

    @property
    def is_on(self) -> bool:
        return self.coordinator.boost_active

    @property
    def extra_state_attributes(self):
        c = self.coordinator
        low, high = c.boost_limits
        try:
            actual = float(c.data.get(OID_WW_ACTUAL))
        except (TypeError, ValueError):
            actual = None

        return {
            "boost_aktiv": c.boost_active,
            "boost_ziel": c.boost_target,
            "boost_fortschritt_pct": None if actual is None else round(min(100.0, actual / c.boost_target * 100.0), 1),
            "ist_temperatur": actual,
            "gespeicherter_sollwert": c.saved_setpoint,
            "sollwert_min": low,
            "sollwert_max": high,
        }

    async def async_turn_on(self, **kwargs):
        await self.coordinator.async_boost_start()

    async def async_turn_off(self, **kwargs):
        await self.coordinator.async_boost_stop()
