# Ochsner Web2Com

Direkte Home-Assistant-Anbindung an `http://<W2C-IP>/ws` über SOAP. Der externe PHP-Server und `phpMQTT.php` werden nicht mehr benötigt.

Optional können gelesene Werte über die bereits in Home Assistant eingerichtete MQTT-Integration retained unter `web2com/<OID>` veröffentlicht werden.

Vor dem Upgrade die alte Integration entfernen, Dateien ersetzen, Home Assistant neu starten und neu einrichten. Standard-W2C-IP: `192.168.0.20`.

Für den manuellen Wasser Switch (switch.ochsner_w2c_warmwasser_manuell) müssen folgende Automatisierungen angelegt werden:

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
