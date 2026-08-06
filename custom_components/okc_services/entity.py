"""Shared device information for OKC Services entities."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo

from .const import CONF_MATCHED_ADDRESS, DOMAIN


def okc_device_info(entry: ConfigEntry) -> DeviceInfo:
    """Return the device all entities for this address belong to."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.data.get(CONF_MATCHED_ADDRESS) or entry.title,
        manufacturer="City of Oklahoma City",
        model="Municipal services",
        configuration_url="https://data.okc.gov/",
    )
