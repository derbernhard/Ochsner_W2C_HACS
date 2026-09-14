# Ochsner Web2Com

Direkte Home-Assistant-Anbindung an `http://<W2C-IP>/ws` über SOAP. Ein externen PHP-Server wird nicht mehr benötigt.




Optional können gelesene Werte über die bereits in Home Assistant eingerichtete MQTT-Integration retained unter `web2com/<OID>` veröffentlicht werden.

Für den manuellen Wasser Switch (switch.ochsner_w2c_warmwasser_manuell) müssen folgende Automatisierungen angelegt werden:

<details>
<summary>Automatisierung YAML Code</summary>

### Ochsner Warmwasser manuell ein

```yaml
alias: Ochsner Warmwasser manuell ein
description: ''
triggers:
  - trigger: state
    entity_id:
      - switch.ochsner_w2c_warmwasser_manuell
    to: 'on'
conditions:
  - condition: numeric_state
    entity_id: sensor.ochsner_w2c_warmwasser_ist_temperatur
    below: 40
actions:
  - wait_for_trigger:
      - trigger: numeric_state
        entity_id:
          - sensor.ochsner_w2c_warmwasser_ist_temperatur
        above: 48
  - action: switch.turn_off
    data: {}
    target:
      entity_id: switch.ochsner_w2c_warmwasser_manuell
mode: single
```
### Ochsner Warmwasser manuell aus

```yaml
alias: Ochsner Warmwasser manuell aus
description: ''
triggers:
  - trigger: state
    entity_id:
      - switch.ochsner_w2c_warmwasser_manuell
conditions:
  - condition: numeric_state
    entity_id: sensor.ochsner_w2c_warmwasser_ist_temperatur
    above: 45
actions:
  - action: switch.turn_off
    data: {}
    target:
      entity_id: switch.ochsner_w2c_warmwasser_manuell
mode: single
```
</details>
