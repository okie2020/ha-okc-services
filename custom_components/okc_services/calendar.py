"""Calendar platform exposing OKC waste collection pickups."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import OKCConfigEntry
from .const import (
    ATTRIBUTION,
    SERVICE_BULKY,
    SERVICE_LABELS,
    SERVICE_RECYCLE,
    SERVICE_TRASH,
)
from .coordinator import OKCScheduleCoordinator
from .entity import okc_device_info

SERVICE_ORDER = (SERVICE_TRASH, SERVICE_RECYCLE, SERVICE_BULKY)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OKCConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the collection calendar."""
    async_add_entities([OKCCollectionCalendar(entry.runtime_data.schedule, entry)])


class OKCCollectionCalendar(CoordinatorEntity[OKCScheduleCoordinator], CalendarEntity):
    """A calendar of upcoming trash, recycling and bulky waste pickups."""

    _attr_has_entity_name = True
    _attr_name = "Collection schedule"
    _attr_attribution = ATTRIBUTION
    _attr_icon = "mdi:trash-can-outline"

    def __init__(
        self, coordinator: OKCScheduleCoordinator, entry: OKCConfigEntry
    ) -> None:
        """Initialise the calendar entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_collection_calendar"
        self._attr_device_info = okc_device_info(entry)

    def _build_events(self, start: date, end: date) -> list[CalendarEvent]:
        """Build all-day events for every pickup falling in the window."""
        data = self.coordinator.data
        if data is None:
            return []

        events: list[CalendarEvent] = []
        for service in SERVICE_ORDER:
            label = SERVICE_LABELS[service]
            zone = data.zones.get(service)
            provider = zone.provider if zone else ""
            route = zone.route if zone else ""

            for day in data.dates.get(service, []):
                if day < start or day > end:
                    continue
                description_parts = []
                if route:
                    description_parts.append(f"Route {route}")
                if provider:
                    description_parts.append(f"Provider: {provider}")

                events.append(
                    CalendarEvent(
                        summary=f"{label} pickup",
                        # All-day events are exclusive of the end date.
                        start=day,
                        end=day + timedelta(days=1),
                        description=" • ".join(description_parts) or None,
                        uid=f"{self._attr_unique_id}_{service}_{day.isoformat()}",
                    )
                )

        events.sort(key=lambda event: (event.start, event.summary))
        return events

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming pickup."""
        today = date.today()
        upcoming = self._build_events(today, today + timedelta(days=400))
        return upcoming[0] if upcoming else None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return all pickups in the requested window."""
        return self._build_events(start_date.date(), end_date.date())
