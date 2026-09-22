"""Ochsner W2C integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import W2CApi
from .const import *
from .coordinator import W2CCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_migrate_entry(hass, entry: ConfigEntry) -> bool:
    _LOGGER.debug("Checking Ochsner W2C migration: entry_id=%s version=%s", entry.entry_id, entry.version)
    if entry.version == 1:
        data = dict(entry.data)
        if "w2c_host" not in data:
            data["w2c_host"] = data.get("target_host", "192.168.0.20")
        data.pop("gateway_host", None)
        data.pop("target_host", None)
        hass.config_entries.async_update_entry(entry, data=data, version=2)
        _LOGGER.info("Migrated Ochsner W2C config entry from version 1 to 2")
    return True


async def async_setup_entry(hass, entry: ConfigEntry) -> bool:
    host = entry.data.get(CONF_W2C_HOST)
    _LOGGER.debug("Setting up Ochsner W2C: entry_id=%s version=%s host=%s", entry.entry_id, entry.version, host)
    api = W2CApi(async_get_clientsession(hass), host, entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    coordinator = W2CCoordinator(
        hass, api,
        entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        entry.data.get(CONF_MQTT_ENABLED, False),
        entry.data.get(CONF_MQTT_BASE_TOPIC, DEFAULT_MQTT_BASE_TOPIC),
    )
    _LOGGER.debug("Requesting first Ochsner W2C coordinator refresh")
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.info("Ochsner W2C initialised successfully: host=%s", host)
    return True


async def async_unload_entry(hass, entry: ConfigEntry) -> bool:
    _LOGGER.debug("Unloading Ochsner W2C: entry_id=%s", entry.entry_id)
    coordinator = getattr(entry, "runtime_data", None)
    if coordinator is not None:
        await coordinator.async_shutdown_boost()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
