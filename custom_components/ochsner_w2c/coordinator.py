"""Data update coordinator for Ochsner W2C."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import W2CApiError
from .const import (
    DEFAULT_BOOST_TARGET,
    MODE_WW_AUTO,
    MODE_WW_NORMAL,
    OID_WW_ACTUAL,
    OID_WW_MODE,
    OID_WW_SET,
    OIDS,
)

_LOGGER = logging.getLogger(__name__)


class W2CCoordinator(DataUpdateCoordinator):
    """Coordinator mit Warmwasser-Boost-Logik."""

    def __init__(self, hass, api, interval, mqtt_enabled=False, mqtt_base_topic="web2com"):
        super().__init__(hass, _LOGGER, name="Ochsner W2C", update_interval=timedelta(seconds=interval))
        self.api = api
        self.mqtt_enabled = mqtt_enabled
        self.mqtt_base_topic = mqtt_base_topic.rstrip("/")

        # Boost-Zustand
        self.boost_active = False
        self.boost_target = DEFAULT_BOOST_TARGET
        self._saved_setpoint = None

        # Gerätegrenzen des Sollwerts (werden beim ersten Poll gelesen)
        self._boost_min = 35.0
        self._boost_max = 70.0
        self._limits_read = False

        _LOGGER.debug(
            "Coordinator created: interval=%ss mqtt_enabled=%s mqtt_base_topic=%s",
            interval, mqtt_enabled, self.mqtt_base_topic,
        )

    # ------------------------------------------------------------------ #
    # Öffentliche Eigenschaften für die Entitäten
    # ------------------------------------------------------------------ #

    @property
    def boost_limits(self) -> tuple[float, float]:
        return self._boost_min, self._boost_max

    @property
    def saved_setpoint(self) -> float | None:
        return self._saved_setpoint

    # ------------------------------------------------------------------ #
    # Regulärer Poll
    # ------------------------------------------------------------------ #

    async def _async_update_data(self):
        _LOGGER.debug("Starting Ochsner W2C coordinator update")
        try:
            data = await self.api.read_all(OIDS)

            if not self._limits_read:
                await self._read_boost_limits()
            await self._check_boost_end(data)

            if self.mqtt_enabled:
                if "mqtt" not in self.hass.config.components:
                    _LOGGER.warning("MQTT publishing enabled, but Home Assistant MQTT integration is not loaded")
                else:
                    from homeassistant.components import mqtt
                    for oid, value in data.items():
                        await mqtt.async_publish(self.hass, f"{self.mqtt_base_topic}{oid}", str(value), qos=0, retain=True)
                    _LOGGER.debug("Published %s W2C values to MQTT", len(data))

            _LOGGER.debug("Ochsner W2C coordinator update successful: %s values", len(data))
            return data
        except W2CApiError as err:
            _LOGGER.error("Ochsner W2C coordinator update failed: type=%s error=%r", type(err).__name__, err)
            raise UpdateFailed(f"Ochsner W2C update failed: {err}") from err
        except Exception as err:
            _LOGGER.exception("Unexpected error during Ochsner W2C coordinator update")
            raise UpdateFailed(f"Unexpected W2C error: {type(err).__name__}: {err}") from err

    # ------------------------------------------------------------------ #
    # Schreiben
    # ------------------------------------------------------------------ #

    async def async_write(self, oid, value):
        _LOGGER.debug("Coordinator write requested: oid=%s value=%s", oid, value)
        await self.api.write_oid(oid, value)
        await self.async_request_refresh()

    # ------------------------------------------------------------------ #
    # Grenzen
    # ------------------------------------------------------------------ #

    async def _read_boost_limits(self):
        """Einmalig die erlaubten Grenzen des Warmwasser-Sollwerts holen."""
        try:
            low, high = await self.api.read_oid_limits(OID_WW_SET)
        except W2CApiError as err:
            _LOGGER.warning("Boost: Sollwert-Grenzen konnten nicht gelesen werden: %r", err)
            return

        if low is not None:
            self._boost_min = low
        if high is not None:
            self._boost_max = high
        self._limits_read = True
        _LOGGER.info("Warmwasser-Sollwert-Grenzen vom Gerät: min=%s max=%s", self._boost_min, self._boost_max)
        self.async_update_listeners()

    def clamp_target(self, value: float) -> float:
        return max(self._boost_min, min(self._boost_max, float(value)))

    # ------------------------------------------------------------------ #
    # Boost-Logik
    # ------------------------------------------------------------------ #

    async def async_boost_start(self, target=None):
        """Boost starten: bisherigen Sollwert merken, Ziel setzen, Betriebsart umstellen."""
        if target is not None:
            self.boost_target = float(target)

        clamped = self.clamp_target(self.boost_target)
        if clamped != self.boost_target:
            _LOGGER.warning(
                "Boost-Ziel %.1f °C auf Gerätegrenzen begrenzt: %.1f °C (min=%s max=%s)",
                self.boost_target, clamped, self._boost_min, self._boost_max,
            )
            self.boost_target = clamped

        if self.boost_active:
            _LOGGER.debug("Boost already active, target updated to %.1f °C", self.boost_target)
            await self.api.write_oid(OID_WW_SET, self.boost_target)
            await self.async_request_refresh()
            return

        try:
            self._saved_setpoint = float(self.data.get(OID_WW_SET))
        except (TypeError, ValueError):
            self._saved_setpoint = None
            _LOGGER.warning(
                "Boost: bisheriger Sollwert konnte nicht gelesen werden, "
                "Rueckstellung erfolgt auf %.1f °C", self.boost_target,
            )

        _LOGGER.info(
            "Warmwasser-Boost gestartet: ziel=%.1f °C vorher=%s",
            self.boost_target, self._saved_setpoint,
        )

        await self.api.write_oid(OID_WW_SET, self.boost_target)
        await self.api.write_oid(OID_WW_MODE, MODE_WW_NORMAL)

        self.boost_active = True
        await self.async_request_refresh()

    async def async_boost_stop(self):
        """Boost manuell beenden und alles zurücksetzen."""
        if not self.boost_active:
            return
        _LOGGER.info("Warmwasser-Boost manuell beendet")
        await self._reset_boost()

    async def _check_boost_end(self, data):
        """Beendet den Boost, sobald die Zieltemperatur erreicht ist."""
        if not self.boost_active:
            return

        try:
            actual = float(data.get(OID_WW_ACTUAL))
        except (TypeError, ValueError):
            return

        if actual < self.boost_target:
            return

        _LOGGER.info(
            "Warmwasser-Boost beendet (Zieltemperatur erreicht): ist=%s ziel=%.1f",
            actual, self.boost_target,
        )
        await self._reset_boost()

    async def _reset_boost(self):
        """Betriebsart und Sollwert wiederherstellen."""
        restore = self._saved_setpoint
        if restore is None:
            restore = self.boost_target

        try:
            await self.api.write_oid(OID_WW_MODE, MODE_WW_AUTO)
            await self.api.write_oid(OID_WW_SET, restore)
        except W2CApiError as err:
            _LOGGER.error("Warmwasser-Boost konnte nicht zurueckgesetzt werden: %r", err)
            # Zustand bleibt aktiv, damit der naechste Poll es erneut versucht
            return

        self.boost_active = False
        self._saved_setpoint = None
        await self.async_request_refresh()

    async def async_shutdown_boost(self):
        """Beim Entladen aufrufen, damit der Boost nicht stehen bleibt."""
        if self.boost_active:
            _LOGGER.info("Integration wird entladen, Warmwasser-Boost wird zurueckgesetzt")
            await self._reset_boost()
