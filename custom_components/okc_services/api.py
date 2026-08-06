"""Async client for the City of Oklahoma City ArcGIS open data services."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

import aiohttp

from .const import (
    AGOL_PROXY,
    ARCGIS_GEOCODE_URL,
    LAYER_BULKY_DATES,
    LAYER_BULKY_ZONES,
    LAYER_EMERGENCY,
    LAYER_RECYCLE_DATES,
    LAYER_RECYCLE_ZONES,
    LAYER_TRASH_ZONES,
    SERVICE_BULKY,
    SERVICE_RECYCLE,
    SERVICE_TRASH,
    WEEKDAYS,
)

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)

# "Aug  6 2026 12:28PM" — single-digit days are space padded.
_REPORTED_TIME_FMT = "%b %d %Y %I:%M%p"


class OKCApiError(Exception):
    """Raised when an OKC open data request fails."""


class AddressNotFoundError(OKCApiError):
    """Raised when an address cannot be geocoded."""


class OutsideServiceAreaError(OKCApiError):
    """Raised when an address falls outside every OKC collection zone."""


@dataclass
class GeocodeResult:
    """A geocoded address."""

    latitude: float
    longitude: float
    matched_address: str
    score: float


@dataclass
class ZoneInfo:
    """A collection zone a property belongs to."""

    route: str
    pickup_day: str
    provider: str


@dataclass
class Incident:
    """A live emergency response incident."""

    uid: str
    call_type: str
    title: str
    address: str
    reported_time: datetime | None
    latitude: float
    longitude: float
    distance_km: float


@dataclass
class ScheduleData:
    """Collection schedule for a single property."""

    zones: dict[str, ZoneInfo] = field(default_factory=dict)
    dates: dict[str, list[date]] = field(default_factory=dict)

    def next_date(self, service: str) -> date | None:
        """Return the next upcoming pickup date for a service."""
        today = date.today()
        for day in self.dates.get(service, []):
            if day >= today:
                return day
        return None


def _layer_url(layer: tuple[str, str, int]) -> str:
    item_id, path, index = layer
    return AGOL_PROXY.format(item_id=item_id, path=path, layer=index)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points in kilometres."""
    radius = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(a))


def _parse_reported_time(raw: str | None) -> datetime | None:
    """Parse the free-text Reported_Time field into a naive local datetime."""
    if not raw:
        return None
    cleaned = re.sub(r"\s+", " ", raw).strip()
    try:
        return datetime.strptime(cleaned, _REPORTED_TIME_FMT)
    except ValueError:
        _LOGGER.debug("Could not parse Reported_Time %r", raw)
        return None


def _epoch_ms_to_date(value: Any) -> date | None:
    """ArcGIS returns dates as epoch milliseconds, UTC."""
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc).date()
    except (TypeError, ValueError, OverflowError, OSError):
        return None


class OKCClient:
    """Thin async wrapper over the OKC ArcGIS feature services."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialise the client."""
        self._session = session

    async def _get_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        """GET a URL and decode the ArcGIS JSON response."""
        try:
            async with self._session.get(
                url, params=params, timeout=REQUEST_TIMEOUT
            ) as resp:
                resp.raise_for_status()
                # ArcGIS frequently serves JSON as text/plain.
                text = await resp.text()
        except asyncio.TimeoutError as err:
            raise OKCApiError(f"Timeout contacting {url}") from err
        except aiohttp.ClientError as err:
            raise OKCApiError(f"Error contacting {url}: {err}") from err

        try:
            data = json.loads(text)
        except ValueError as err:
            raise OKCApiError(f"Non-JSON response from {url}") from err

        if isinstance(data, dict) and "error" in data:
            raise OKCApiError(f"ArcGIS error from {url}: {data['error']}")
        return data

    async def _query(self, layer: tuple[str, str, int], **params: Any) -> list[dict]:
        """Run a feature-service query and return the raw features."""
        query = {"f": "json", **params}
        data = await self._get_json(f"{_layer_url(layer)}/query", query)
        return data.get("features", []) or []

    async def geocode(self, address: str) -> GeocodeResult:
        """Geocode a street address using the public ArcGIS World geocoder."""
        params = {
            "f": "json",
            "singleLine": address,
            "countryCode": "USA",
            "maxLocations": 1,
            "outFields": "Match_addr,Addr_type",
        }
        data = await self._get_json(ARCGIS_GEOCODE_URL, params)
        candidates = data.get("candidates") or []
        if not candidates:
            raise AddressNotFoundError(f"No match for address: {address}")

        best = candidates[0]
        location = best.get("location") or {}
        if "x" not in location or "y" not in location:
            raise AddressNotFoundError(f"Geocoder returned no coordinates for {address}")

        return GeocodeResult(
            latitude=float(location["y"]),
            longitude=float(location["x"]),
            matched_address=best.get("address") or address,
            score=float(best.get("score") or 0),
        )

    async def _zone_at_point(
        self,
        layer: tuple[str, str, int],
        latitude: float,
        longitude: float,
        route_field: str,
        day_field: str,
        provider_field: str,
    ) -> ZoneInfo | None:
        """Find the collection zone polygon containing a point."""
        geometry = json.dumps(
            {"x": longitude, "y": latitude, "spatialReference": {"wkid": 4326}}
        )
        features = await self._query(
            layer,
            geometry=geometry,
            geometryType="esriGeometryPoint",
            inSR=4326,
            spatialRel="esriSpatialRelIntersects",
            outFields="*",
            returnGeometry="false",
        )
        if not features:
            return None

        attrs = features[0].get("attributes") or {}
        route = attrs.get(route_field)
        if route is None:
            return None

        return ZoneInfo(
            route=str(route).strip(),
            pickup_day=str(attrs.get(day_field) or "").strip(),
            provider=str(attrs.get(provider_field) or "").strip(),
        )

    async def _pickup_dates(
        self, layer: tuple[str, str, int], route_field: str, date_field: str, route: str
    ) -> list[date]:
        """Fetch every published pickup date for a route, sorted ascending.

        The published tables hold only a rolling window of dates, so they are
        small enough to filter client-side. Doing so avoids depending on the
        service's date-literal dialect.
        """
        safe_route = route.replace("'", "''")
        features = await self._query(
            layer,
            where=f"{route_field}='{safe_route}'",
            outFields=f"{route_field},{date_field}",
            returnGeometry="false",
            orderByFields=f"{date_field} ASC",
        )

        cutoff = date.today() - timedelta(days=1)
        dates = {
            parsed
            for feature in features
            if (parsed := _epoch_ms_to_date((feature.get("attributes") or {}).get(date_field)))
            is not None
            and parsed >= cutoff
        }
        return sorted(dates)

    def _weekly_dates(self, pickup_day: str, horizon_days: int) -> list[date]:
        """Expand a weekday name into recurring dates within the horizon."""
        weekday = WEEKDAYS.get(pickup_day.strip().lower())
        if weekday is None:
            return []

        today = date.today()
        offset = (weekday - today.weekday()) % 7
        first = today + timedelta(days=offset)
        weeks = horizon_days // 7
        return [first + timedelta(weeks=i) for i in range(weeks + 1)]

    async def async_get_schedule(
        self, latitude: float, longitude: float, trash_horizon_days: int
    ) -> ScheduleData:
        """Resolve all three collection zones and their upcoming dates."""
        trash_zone, recycle_zone, bulky_zone = await asyncio.gather(
            self._zone_at_point(
                LAYER_TRASH_ZONES,
                latitude,
                longitude,
                "ROUTE",
                "PICKUPDAY",
                "SERVICE_PROVIDER",
            ),
            self._zone_at_point(
                LAYER_RECYCLE_ZONES,
                latitude,
                longitude,
                "Route",
                "PickupDay",
                "ServiceProvider",
            ),
            self._zone_at_point(
                LAYER_BULKY_ZONES,
                latitude,
                longitude,
                "ROUTE",
                "PICKUPDAY",
                "SERVICE_PROVIDER",
            ),
        )

        if not any((trash_zone, recycle_zone, bulky_zone)):
            raise OutsideServiceAreaError(
                "That location is not inside any City of Oklahoma City collection zone"
            )

        schedule = ScheduleData()
        for service, zone in (
            (SERVICE_TRASH, trash_zone),
            (SERVICE_RECYCLE, recycle_zone),
            (SERVICE_BULKY, bulky_zone),
        ):
            if zone is not None:
                schedule.zones[service] = zone

        # Recycling and bulky waste have authoritative published date tables.
        tasks = []
        if recycle_zone is not None:
            tasks.append(
                (
                    SERVICE_RECYCLE,
                    self._pickup_dates(
                        LAYER_RECYCLE_DATES,
                        "MeterReadingUnit",
                        "PickUpDate",
                        recycle_zone.route,
                    ),
                )
            )
        if bulky_zone is not None:
            tasks.append(
                (
                    SERVICE_BULKY,
                    self._pickup_dates(
                        LAYER_BULKY_DATES, "RouteNumber", "PickupDate", bulky_zone.route
                    ),
                )
            )

        if tasks:
            results = await asyncio.gather(*(task for _, task in tasks))
            for (service, _), dates in zip(tasks, results):
                schedule.dates[service] = dates

        # Trash is a simple weekly service with no published date table.
        if trash_zone is not None:
            schedule.dates[SERVICE_TRASH] = self._weekly_dates(
                trash_zone.pickup_day, trash_horizon_days
            )

        return schedule

    async def async_get_incidents(
        self,
        home_lat: float,
        home_lon: float,
        radius_km: float,
        call_types: list[str] | None = None,
    ) -> list[Incident]:
        """Fetch current fire and police responses near the home location."""
        features = await self._query(
            LAYER_EMERGENCY,
            where="1=1",
            outFields="*",
            returnGeometry="true",
            outSR=4326,
        )

        wanted = {t.casefold() for t in call_types} if call_types else None
        incidents: list[Incident] = []

        for feature in features:
            geometry = feature.get("geometry") or {}
            attrs = feature.get("attributes") or {}
            lon, lat = geometry.get("x"), geometry.get("y")
            if lon is None or lat is None:
                continue

            call_type = str(attrs.get("Call_Type") or "Unknown").strip()
            if wanted is not None and not any(w in call_type.casefold() for w in wanted):
                continue

            distance = haversine_km(home_lat, home_lon, float(lat), float(lon))
            if distance > radius_km:
                continue

            object_id = attrs.get("ObjectID")
            incidents.append(
                Incident(
                    uid=str(object_id),
                    call_type=call_type,
                    title=str(attrs.get("InfoTitle") or call_type).strip(),
                    address=str(attrs.get("Address") or "").strip(),
                    reported_time=_parse_reported_time(attrs.get("Reported_Time")),
                    latitude=float(lat),
                    longitude=float(lon),
                    distance_km=round(distance, 2),
                )
            )

        incidents.sort(key=lambda item: item.distance_km)
        return incidents
