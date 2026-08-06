"""Data update coordinators for OKC Services."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import Incident, OKCApiError, OKCClient, ScheduleData, WorkZone
from .const import (
    CONF_INCIDENT_RADIUS,
    CONF_INCIDENT_TYPES,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_WORK_ZONE_RADIUS,
    CONF_WORK_ZONE_TYPES,
    DEFAULT_INCIDENT_RADIUS,
    DEFAULT_WORK_ZONE_RADIUS,
    DOMAIN,
    INCIDENT_SCAN_INTERVAL_MINUTES,
    SCHEDULE_SCAN_INTERVAL_HOURS,
    TRASH_HORIZON_DAYS,
    WORK_ZONE_SCAN_INTERVAL_MINUTES,
)

_LOGGER = logging.getLogger(__name__)


class OKCScheduleCoordinator(DataUpdateCoordinator[ScheduleData]):
    """Keeps the trash, recycling and bulky waste schedule up to date."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: OKCClient
    ) -> None:
        """Initialise the schedule coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_schedule",
            update_interval=timedelta(hours=SCHEDULE_SCAN_INTERVAL_HOURS),
            config_entry=entry,
        )
        self._client = client
        self._latitude = entry.data[CONF_LATITUDE]
        self._longitude = entry.data[CONF_LONGITUDE]

    async def _async_update_data(self) -> ScheduleData:
        try:
            return await self._client.async_get_schedule(
                self._latitude, self._longitude, TRASH_HORIZON_DAYS
            )
        except OKCApiError as err:
            raise UpdateFailed(f"Could not refresh collection schedule: {err}") from err


class OKCIncidentCoordinator(DataUpdateCoordinator[list[Incident]]):
    """Polls the live fire and police emergency response feed."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: OKCClient
    ) -> None:
        """Initialise the incident coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_incidents",
            update_interval=timedelta(minutes=INCIDENT_SCAN_INTERVAL_MINUTES),
            config_entry=entry,
        )
        self._client = client
        self._entry = entry
        self._latitude = entry.data[CONF_LATITUDE]
        self._longitude = entry.data[CONF_LONGITUDE]

    @property
    def home_coordinates(self) -> tuple[float, float]:
        """Return the configured home location."""
        return self._latitude, self._longitude

    async def _async_update_data(self) -> list[Incident]:
        options = self._entry.options
        radius = options.get(CONF_INCIDENT_RADIUS, DEFAULT_INCIDENT_RADIUS)
        raw_types = options.get(CONF_INCIDENT_TYPES) or []
        call_types = [t for t in raw_types if t] or None

        try:
            return await self._client.async_get_incidents(
                self._latitude, self._longitude, radius, call_types
            )
        except OKCApiError as err:
            raise UpdateFailed(f"Could not refresh emergency responses: {err}") from err


class OKCWorkZoneCoordinator(DataUpdateCoordinator[list[WorkZone]]):
    """Polls the active street work zone feed."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: OKCClient
    ) -> None:
        """Initialise the work zone coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_work_zones",
            update_interval=timedelta(minutes=WORK_ZONE_SCAN_INTERVAL_MINUTES),
            config_entry=entry,
        )
        self._client = client
        self._entry = entry
        self._latitude = entry.data[CONF_LATITUDE]
        self._longitude = entry.data[CONF_LONGITUDE]

    async def _async_update_data(self) -> list[WorkZone]:
        options = self._entry.options
        radius = options.get(CONF_WORK_ZONE_RADIUS, DEFAULT_WORK_ZONE_RADIUS)
        raw_types = options.get(CONF_WORK_ZONE_TYPES) or []
        work_types = [t for t in raw_types if t] or None

        try:
            return await self._client.async_get_work_zones(
                self._latitude, self._longitude, radius, work_types
            )
        except OKCApiError as err:
            raise UpdateFailed(f"Could not refresh work zones: {err}") from err
