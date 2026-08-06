"""Geolocation platform placing OKC emergency responses on the HA map."""

from __future__ import annotations

import logging

from homeassistant.components.geo_location import GeolocationEvent
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import OKCConfigEntry
from .api import Incident, WorkZone
from .const import ATTRIBUTION
from .coordinator import OKCIncidentCoordinator, OKCWorkZoneCoordinator
from .icons import incident_picture, work_zone_picture

_LOGGER = logging.getLogger(__name__)

SOURCE = "okc_emergency"
WORK_ZONE_SOURCE = "okc_work_zones"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OKCConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up dynamic incident and work zone markers."""
    runtime = entry.runtime_data

    if runtime.incidents is not None:
        _track(entry, runtime.incidents, async_add_entities, OKCIncidentEvent)

    if runtime.work_zones is not None:
        _track(entry, runtime.work_zones, async_add_entities, OKCWorkZoneEvent)


def _track(
    entry: OKCConfigEntry,
    coordinator: OKCIncidentCoordinator | OKCWorkZoneCoordinator,
    async_add_entities: AddEntitiesCallback,
    entity_class: type[OKCIncidentEvent] | type[OKCWorkZoneEvent],
) -> None:
    """Add a marker for every new item; stale ones remove themselves."""
    known: set[str] = set()

    @callback
    def _sync() -> None:
        items = coordinator.data or []
        current = {item.uid for item in items}

        new = [item for item in items if item.uid not in known]
        if new:
            async_add_entities(entity_class(coordinator, item.uid) for item in new)

        known.clear()
        known.update(current)

    _sync()
    entry.async_on_unload(coordinator.async_add_listener(_sync))


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

        This is what the map falls back to if the picture below ever fails to
        render, and it is the label shown everywhere else in the UI, so it is
        kept free of the address and of separators like an em dash.
        """
        incident = self._incident
        return incident.call_type if incident else None

    @property
    def entity_picture(self) -> str | None:
        """Return a colour-coded icon for the marker.

        The map only accepts initials or a picture, never an mdi icon, so the
        icon is supplied as an inline SVG data URI.
        """
        incident = self._incident
        return incident_picture(incident.call_type) if incident else None

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


class OKCWorkZoneEvent(CoordinatorEntity[OKCWorkZoneCoordinator], GeolocationEvent):
    """A single active work zone shown on the map."""

    _attr_should_poll = False
    _attr_source = WORK_ZONE_SOURCE
    _attr_attribution = ATTRIBUTION
    _attr_unit_of_measurement = UnitOfLength.MILES
    _attr_icon = "mdi:traffic-cone"

    def __init__(self, coordinator: OKCWorkZoneCoordinator, uid: str) -> None:
        """Initialise the work zone marker.

        Like incidents these carry no unique_id. Work zones do have a stable
        WZ- number, but they still come and go as projects finish, and a
        registry entry per finished project would accumulate indefinitely.
        """
        super().__init__(coordinator)
        self._uid = uid

    @property
    def _zone(self) -> WorkZone | None:
        for zone in self.coordinator.data or []:
            if zone.uid == self._uid:
                return zone
        return None

    @property
    def available(self) -> bool:
        return super().available and self._zone is not None

    @property
    def name(self) -> str | None:
        zone = self._zone
        return zone.work_type if zone else None

    @property
    def entity_picture(self) -> str | None:
        zone = self._zone
        if zone is None:
            return None
        return work_zone_picture(
            zone.road_closed, zone.lane_closed, zone.sidewalk_closed
        )

    @property
    def distance(self) -> float | None:
        zone = self._zone
        return zone.distance_mi if zone else None

    @property
    def latitude(self) -> float | None:
        zone = self._zone
        return zone.latitude if zone else None

    @property
    def longitude(self) -> float | None:
        zone = self._zone
        return zone.longitude if zone else None

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        zone = self._zone
        if zone is None:
            return {}
        return {
            "work_type": zone.work_type,
            "location": zone.location,
            "work_zone_number": zone.number,
            "impact": zone.impact,
            "start_date": zone.start_date.isoformat() if zone.start_date else None,
            "end_date": zone.end_date.isoformat() if zone.end_date else None,
            "road_closed": zone.road_closed,
            "lane_closed": zone.lane_closed,
            "sidewalk_closed": zone.sidewalk_closed,
            "right_of_way_work": zone.right_of_way_work,
            "directions_affected": zone.directions,
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Remove the marker once the project drops off the feed."""
        if self._zone is None:
            self.hass.async_create_task(self.async_remove(force_remove=True))
            return
        super()._handle_coordinator_update()
