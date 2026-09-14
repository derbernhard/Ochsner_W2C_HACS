# Ochsner W2C Direct 0.2.0

Direkte Home-Assistant-Anbindung an `http://<W2C-IP>/ws` über SOAP. Der externe PHP-Server und `phpMQTT.php` werden nicht mehr benötigt.

Optional können gelesene Werte über die bereits in Home Assistant eingerichtete MQTT-Integration retained unter `web2com/<OID>` veröffentlicht werden.

Vor dem Upgrade die alte Integration entfernen, Dateien ersetzen, Home Assistant neu starten und neu einrichten. Standard-W2C-IP: `192.168.0.20`.
