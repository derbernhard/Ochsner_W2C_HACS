from homeassistant.components.select import SelectEntity
from .entity import Entity
HEAT={0:'0: Standby Betrieb',1:'1: Automatikbetrieb',4:'4: Normalbetrieb',5:'5: Sparbetrieb',6:'6: Sommerbetrieb',7:'7: Handbetrieb heizen',8:'8: Handbetrieb kühlen'};WATER={0:'0: Keine Ladung',1:'1: Automatikbetrieb',2:'2: Normaltemperatur',3:'3: Nach Heizbetrieb',4:'4: Aktorentest',5:'5: Gemäß Führungskreis'}
async def async_setup_entry(hass,e,add):add([Mode(e.runtime_data,e,'heating_mode','Betriebswahl Heizung','/1/2/4/107/0',HEAT),Mode(e.runtime_data,e,'water_mode','Betriebswahl Warmwasser','/1/2/7/107/0',WATER)])
class Mode(Entity,SelectEntity):
 def __init__(self,c,e,key,name,oid,m):super().__init__(c,e,key);self._attr_name=name;self.oid=oid;self.map=m;self._attr_options=list(m.values())
 @property
 def current_option(self):
  try:return self.map.get(int(self.coordinator.data.get(self.oid)))
  except:return None
 async def async_select_option(self,option):await self.coordinator.write(self.oid,int(option.split(':',1)[0]))
