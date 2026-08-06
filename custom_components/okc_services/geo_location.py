"""Geolocation platform placing OKC emergency responses on the HA map."""

from __future__ import annotations

import logging

from homeassistant.components.geo_location import GeolocationEvent
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import OKCConfigEntry
from .api import Incident
from .const import ATTRIBUTION
from .coordinator import OKCIncidentCoordinator

_LOGGER = logging.getLogger(__name__)

SOURCE = "okc_emergency"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OKCConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up dynamic incident markers."""
    coordinator = entry.runtime_data.incidents
    if coordinator is None:
        return

    known: set[str] = set()

    @callback
    def _sync_incidents() -> None:
        """Add markers for new incidents; stale ones remove themselves."""
        incidents = coordinator.data or []
        current = {incident.uid for incident in incidents}

        new = [
            incident for incident in incidents if incident.uid not in known
        ]
        if new:
            async_add_entities(
                OKCIncidentEvent(coordinator, incident.uid) for incident in new
            )

        known.clear()
        known.update(current)

    _sync_incidents()
    entry.async_on_unload(coordinator.async_add_listener(_sync_incidents))


class OKCIncidentEvent(CoordinatorEntity[OKCIncidentCoordinator], GeolocationEvent):
    """A single emergency response shown on the map."""

    _attr_should_poll = False
    _attr_source = SOURCE
    _attr_attribution = ATTRIBUTION
    _attr_unit_of_measurement = UnitOfLength.MILES
    _attr_icon = "mdi:car-emergency"

    def __init__(self, coordinator: OKCIncidentCoordinator, uid: str) -> None:
        """Initialise the incident marker.

        Deliberately has no unique_id: incidents are short lived and a
        registry entry per accident would accumulate indefinitely.
        """
        super().__init__(coordinator)
        self._uid = uid

    @property
    def _incident(self) -> Incident | None:
        for incident in self.coordinator.data or []:
            if incident.uid == self._uid:
                return incident
        return None

    @property
    def available(self) -> bool:
        return super().available and self._incident is not None

    @property
    def name(self) -> str | None:
        """Return the call type alone.

        The map card builds its marker label from the first letter of each
        word in this name, so anything appended here (an address, or a
        separator like an em dash) leaks into the badge as noise. Call type
        only yields a clean "NA" or "IA"; the address stays an attribute.
        """
        incident = self._incident
        return incident.call_type if incident else None

    @property
    def distance(self) -> float | None:
        incident = self._incident
        return incident.distance_mi if incident else None

    @property
    def latitude(self) -> float | None:
        incident = self._incident
        return incident.latitude if incident else None

    @property
    def longitude(self) -> float | None:
        incident = self._incident
        return incident.longitude if incident else None

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        incident = self._incident
        if incident is None:
            return {}
        return {
            "call_type": incident.call_type,
            "title": incident.title,
            "address": incident.address,
            "reported_time": (
                incident.reported_time.isoformat() if incident.reported_time else None
            ),
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Remove the marker once the incident clears the live feed."""
        if self._incident is None:
            self.hass.async_create_task(self.async_remove(force_remove=True))
            return
        super()._handle_coordinator_update()
