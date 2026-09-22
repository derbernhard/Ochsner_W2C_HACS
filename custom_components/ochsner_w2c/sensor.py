from dataclasses import dataclass
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription, SensorDeviceClass
from homeassistant.const import UnitOfTemperature, PERCENTAGE
from .entity import W2CEntity

HEAT={0:'Abgeschaltet',1:'Automatik'}; HEATMODE={0:'0: Standby Betrieb',1:'1: Automatikbetrieb',4:'4: Normalbetrieb',5:'5: Sparbetrieb',6:'6: Sommerbetrieb',7:'7: Handbetrieb heizen',8:'8: Handbetrieb kühlen'}; WATER={0:'Abgeschaltet',1:'Automatik'}; WATERMODE={0:'0: Keine Ladung',1:'1: Automatikbetrieb',2:'2: Normaltemperatur',3:'3: Nach Heizbetrieb',4:'4: Aktorentest',5:'5: Gemäß Führungskreis'}

@dataclass(frozen=True,kw_only=True)
class D(SensorEntityDescription):
    oid: str
    mapping: dict | None = None

DS=(
    D(key='temp_out',name='Außentemperatur',oid='/1/2/4/119/1',device_class=SensorDeviceClass.TEMPERATURE,native_unit_of_measurement=UnitOfTemperature.CELSIUS),
    D(key='temp_room',name='Raumtemperatur',oid='/1/2/4/119/3',device_class=SensorDeviceClass.TEMPERATURE,native_unit_of_measurement=UnitOfTemperature.CELSIUS),
    D(key='humidity',name='Relative Luftfeuchte',oid='/1/2/4/119/7',device_class=SensorDeviceClass.HUMIDITY,native_unit_of_measurement=PERCENTAGE),
    D(key='status_heater',name='Status Heizkreis',oid='/1/2/4/119/0',mapping=HEAT),
    D(key='status_heater_value',name='Status Heizkreis Betriebswahl',oid='/1/2/4/107/0',mapping=HEATMODE),
    D(key='ww_ist',name='Warmwasser IST-Temperatur',oid='/1/2/7/121/1',device_class=SensorDeviceClass.TEMPERATURE,native_unit_of_measurement=UnitOfTemperature.CELSIUS),
    D(key='ww_soll',name='Warmwasser SOLL-Temperatur',oid='/1/2/7/121/2',device_class=SensorDeviceClass.TEMPERATURE,native_unit_of_measurement=UnitOfTemperature.CELSIUS),
    D(key='status_water',name='Status Warmwasser',oid='/1/2/7/121/0',mapping=WATER),
    D(key='status_water_value',name='Status Warmwasser Betriebswahl',oid='/1/2/7/107/0',mapping=WATERMODE),
)

async def async_setup_entry(hass, e, add):
    add([S(e.runtime_data, e, d) for d in DS])
    add([BoostProgress(e.runtime_data, e)])

class S(W2CEntity, SensorEntity):
    def __init__(self, c, e, d):
        super().__init__(c, e, d.key)
        self.entity_description = d

    @property
    def native_value(self):
        v = self.coordinator.data.get(self.entity_description.oid)
        if self.entity_description.mapping:
            try:
                return self.entity_description.mapping.get(int(v), str(v))
            except (TypeError, ValueError):
                return str(v)
        return v

class BoostProgress(W2CEntity, SensorEntity):
    """Fortschritt des Boosts in Prozent, bezogen auf die Zieltemperatur."""

    _attr_name = "Warmwasser Boost Fortschritt"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon = "mdi:progress-clock"

    def __init__(self, c, e):
        super().__init__(c, e, "ww_boost_progress")

    @property
    def native_value(self):
        c = self.coordinator
        if not c.boost_active:
            return 0
        try:
            actual = float(c.data.get('/1/2/7/121/1'))
        except (TypeError, ValueError):
            return None
        if c.boost_target <= 0:
            return None
        return round(min(100.0, actual / c.boost_target * 100.0), 1)
