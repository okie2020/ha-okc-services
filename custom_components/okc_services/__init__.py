"""The OKC Services integration.

Brings City of Oklahoma City waste collection schedules and the live fire and
police emergency response feed into Home Assistant.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import OKCClient
from .const import (
    CONF_INCIDENT_RADIUS,
    CONF_INCIDENTS_ENABLED,
    DEFAULT_INCIDENTS_ENABLED,
    KM_TO_MILES,
)
from .coordinator import OKCIncidentCoordinator, OKCScheduleCoordinator

_LOGGER = logging.getLogger(__name__)

BASE_PLATFORMS: list[Platform] = [Platform.CALENDAR, Platform.SENSOR]
INCIDENT_PLATFORMS: list[Platform] = [Platform.GEO_LOCATION]


@dataclass
class OKCRuntimeData:
    """Runtime objects shared with the platforms."""

    schedule: OKCScheduleCoordinator
    incidents: OKCIncidentCoordinator | None
    # Recorded at setup so unload tears down exactly what was set up, even if
    # the options changed in between.
    platforms: list[Platform] = field(default_factory=list)


type OKCConfigEntry = ConfigEntry[OKCRuntimeData]


async def async_migrate_entry(hass: HomeAssistant, entry: OKCConfigEntry) -> bool:
    """Migrate an old config entry."""
    if entry.version == 1:
        # Version 1 stored the incident radius in kilometres. Convert it so an
        # existing setup keeps covering the same ground rather than silently
        # shrinking to 62% of the area the user picked.
        options = dict(entry.options)
        if (radius := options.get(CONF_INCIDENT_RADIUS)) is not None:
            options[CONF_INCIDENT_RADIUS] = round(float(radius) * KM_TO_MILES, 1)

        hass.config_entries.async_update_entry(entry, options=options, version=2)
        _LOGGER.debug("Migrated OKC Services entry to version 2 (radius now miles)")

    return True


async def async_setup_entry(hass: HomeAssistant, entry: OKCConfigEntry) -> bool:
    """Set up OKC Services from a config entry."""
    session = async_get_clientsession(hass)
    client = OKCClient(session)

    schedule = OKCScheduleCoordinator(hass, entry, client)
    await schedule.async_config_entry_first_refresh()

    platforms = list(BASE_PLATFORMS)
    incidents: OKCIncidentCoordinator | None = None

    if entry.options.get(CONF_INCIDENTS_ENABLED, DEFAULT_INCIDENTS_ENABLED):
        incidents = OKCIncidentCoordinator(hass, entry, client)
        await incidents.async_config_entry_first_refresh()
        platforms += INCIDENT_PLATFORMS

    entry.runtime_data = OKCRuntimeData(
        schedule=schedule, incidents=incidents, platforms=platforms
    )

    await hass.config_entries.async_forward_entry_setups(entry, platforms)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OKCConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(
        entry, entry.runtime_data.platforms
    )


async def async_reload_entry(hass: HomeAssistant, entry: OKCConfigEntry) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)
