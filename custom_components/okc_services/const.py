"""Constants for the OKC Services integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "okc_services"

CONF_ADDRESS: Final = "address"
CONF_LATITUDE: Final = "latitude"
CONF_LONGITUDE: Final = "longitude"
CONF_MATCHED_ADDRESS: Final = "matched_address"

CONF_INCIDENT_RADIUS: Final = "incident_radius"
CONF_INCIDENT_TYPES: Final = "incident_types"
CONF_INCIDENTS_ENABLED: Final = "incidents_enabled"

DEFAULT_INCIDENT_RADIUS: Final = 5.0  # kilometres
DEFAULT_INCIDENTS_ENABLED: Final = True

# City of Oklahoma City publishes its open data through ArcGIS Online. The
# public REST proxy path embeds the AGOL item id as the "server" segment, so
# these URLs are fully derivable from the item ids below.
AGOL_PROXY: Final = "https://utility.arcgis.com/usrsvcs/servers/{item_id}/rest/services/{path}/FeatureServer/{layer}"

# The direct gis.okc.gov host sits behind a bot-mitigation WAF that rejects
# non-browser clients, so the AGOL proxy above is the only endpoint that works
# reliably from inside Home Assistant.

ARCGIS_GEOCODE_URL: Final = (
    "https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates"
)

# (item_id, service path, layer index)
LAYER_TRASH_ZONES: Final = ("45426e5e1b31489db9afea603870f724", "OpenData/Utilities", 1)
LAYER_BULKY_ZONES: Final = ("c4455716f4bf4d1dafe6806e0e619de8", "OpenData/Utilities", 2)
LAYER_RECYCLE_ZONES: Final = ("0f286e1243ca4bb39a70e323b1608222", "OpenData/Utilities", 3)
LAYER_BULKY_DATES: Final = ("f3a929a6412d467ba7d8e84d8d152522", "OpenData/Utilities", 10)
LAYER_RECYCLE_DATES: Final = ("170516f158df4fcdaaf4e06382b282e6", "OpenData/Utilities", 11)
LAYER_EMERGENCY: Final = (
    "01c97e2928134efc93157d99f2d23047",
    "OpenData/Public_Safety",
    0,
)

SERVICE_TRASH: Final = "trash"
SERVICE_RECYCLE: Final = "recycle"
SERVICE_BULKY: Final = "bulky"

SERVICE_LABELS: Final = {
    SERVICE_TRASH: "Trash",
    SERVICE_RECYCLE: "Recycling",
    SERVICE_BULKY: "Bulky Waste",
}

# Schedules change rarely; incidents are a live feed.
SCHEDULE_SCAN_INTERVAL_HOURS: Final = 6
INCIDENT_SCAN_INTERVAL_MINUTES: Final = 5

# How far ahead the calendar synthesises weekly trash pickups.
TRASH_HORIZON_DAYS: Final = 120

ATTRIBUTION: Final = "Data provided by the City of Oklahoma City open data portal"

WEEKDAYS: Final = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}
