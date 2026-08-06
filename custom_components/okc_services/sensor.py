"""Sensor platform for OKC Services."""

from __future__ import annotations

from datetime import date

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
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
from .coordinator import OKCIncidentCoordinator, OKCScheduleCoordinator
from .entity import okc_device_info

SERVICES = (SERVICE_TRASH, SERVICE_RECYCLE, SERVICE_BULKY)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OKCConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the OKC sensors."""
    runtime = entry.runtime_data

    entities: list[SensorEntity] = []
    for service in SERVICES:
        entities.append(OKCNextPickupSensor(runtime.schedule, entry, service))
        entities.append(OKCDaysUntilPickupSensor(runtime.schedule, entry, service))

    if runtime.incidents is not None:
        entities.append(OKCIncidentCountSensor(runtime.incidents, entry))

    async_add_entities(entities)


class _ScheduleSensorBase(CoordinatorEntity[OKCScheduleCoordinator], SensorEntity):
    """Common wiring for schedule-derived sensors."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    def __init__(
        self, coordinator: OKCScheduleCoordinator, entry: OKCConfigEntry, service: str
    ) -> None:
        super().__init__(coordinator)
        self._service = service
        self._attr_device_info = okc_device_info(entry)

    @property
    def _next_date(self) -> date | None:
        data = self.coordinator.data
        return data.next_date(self._service) if data else None

    @property
    def available(self) -> bool:
        """Only available when the address falls in a zone for this service."""
        data = self.coordinator.data
        return super().available and bool(data and self._service in data.zones)

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        data = self.coordinator.data
        zone = data.zones.get(self._service) if data else None
        if zone is None:
            return {}
        attrs = {"route": zone.route, "pickup_day": zone.pickup_day}
        if zone.provider:
            attrs["service_provider"] = zone.provider
        return attrs


class OKCNextPickupSensor(_ScheduleSensorBase):
    """Date of the next pickup for a service."""

    _attr_device_class = SensorDeviceClass.DATE

    def __init__(
        self, coordinator: OKCScheduleCoordinator, entry: OKCConfigEntry, service: str
    ) -> None:
        super().__init__(coordinator, entry, service)
        self._attr_name = f"Next {SERVICE_LABELS[service].lower()} pickup"
        self._attr_unique_id = f"{entry.entry_id}_{service}_next_pickup"

    @property
    def native_value(self) -> date | None:
        return self._next_date


class OKCDaysUntilPickupSensor(_ScheduleSensorBase):
    """Whole days until the next pickup for a service."""

    _attr_native_unit_of_measurement = "d"
    _attr_icon = "mdi:calendar-clock"

    def __init__(
        self, coordinator: OKCScheduleCoordinator, entry: OKCConfigEntry, service: str
    ) -> None:
        super().__init__(coordinator, entry, service)
        self._attr_name = f"{SERVICE_LABELS[service]} pickup in"
        self._attr_unique_id = f"{entry.entry_id}_{service}_days_until"

    @property
    def native_value(self) -> int | None:
        next_date = self._next_date
        if next_date is None:
            return None
        return (next_date - date.today()).days


class OKCIncidentCountSensor(CoordinatorEntity[OKCIncidentCoordinator], SensorEntity):
    """Number of active emergency responses within the configured radius."""

    _attr_has_entity_name = True
    _attr_name = "Nearby emergency responses"
    _attr_attribution = ATTRIBUTION
    _attr_icon = "mdi:car-emergency"
    _attr_native_unit_of_measurement = "incidents"

    def __init__(
        self, coordinator: OKCIncidentCoordinator, entry: OKCConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_incident_count"
        self._attr_device_info = okc_device_info(entry)

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data or [])

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        incidents = self.coordinator.data or []
        closest = incidents[0] if incidents else None
        attrs: dict[str, object] = {
            "incidents": [
                {
                    "call_type": incident.call_type,
                    "address": incident.address,
                    "distance_km": incident.distance_km,
                    "reported_time": (
                        incident.reported_time.isoformat()
                        if incident.reported_time
                        else None
                    ),
                    "latitude": incident.latitude,
                    "longitude": incident.longitude,
                }
                for incident in incidents
            ]
        }
        if closest is not None:
            attrs["closest_distance_km"] = closest.distance_km
            attrs["closest_call_type"] = closest.call_type
        return attrs
