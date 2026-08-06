"""Config and options flow for OKC Services."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .api import (
    AddressNotFoundError,
    GeocodeResult,
    OKCApiError,
    OKCClient,
    OutsideServiceAreaError,
)
from .const import (
    CONF_ADDRESS,
    CONF_INCIDENT_RADIUS,
    CONF_INCIDENT_TYPES,
    CONF_INCIDENTS_ENABLED,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MATCHED_ADDRESS,
    CONF_WORK_ZONE_RADIUS,
    CONF_WORK_ZONE_TYPES,
    CONF_WORK_ZONES_ENABLED,
    DEFAULT_INCIDENT_RADIUS,
    DEFAULT_INCIDENTS_ENABLED,
    DEFAULT_WORK_ZONE_RADIUS,
    DEFAULT_WORK_ZONES_ENABLED,
    DOMAIN,
    TRASH_HORIZON_DAYS,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema({vol.Required(CONF_ADDRESS): TextSelector()})

# Common values seen in the Call_Type field; matching is substring based so
# these act as broad categories rather than an exhaustive list.
INCIDENT_TYPE_CHOICES = [
    "Non-Injury Accident",
    "Injury Accident",
    "Fire",
    "Hazmat",
    "Rescue",
    "Medical",
]


# The Worktype vocabulary the city publishes. Matching is substring based, so
# "Street" covers both "Street Repair" and "Street/Sidewalk Repair".
WORK_ZONE_TYPE_CHOICES = [
    "Road Construction",
    "Street Repair",
    "Sidewalk Repair",
    "Street/Sidewalk Repair",
    "Driveway Repair",
    "Utility Maintenance and Repair",
    "Building Construction",
    "Building Demolition",
    "Dumpster/Storage",
    "Miscellaneous",
]


def incident_options_schema(options: Mapping[str, Any]) -> vol.Schema:
    """Build the options schema, defaulted from existing options.

    Shared so the initial setup and the later options flow always offer the
    same choices.
    """
    return vol.Schema(
        {
            vol.Required(
                CONF_INCIDENTS_ENABLED,
                default=options.get(CONF_INCIDENTS_ENABLED, DEFAULT_INCIDENTS_ENABLED),
            ): BooleanSelector(),
            vol.Required(
                CONF_INCIDENT_RADIUS,
                default=options.get(CONF_INCIDENT_RADIUS, DEFAULT_INCIDENT_RADIUS),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0.5,
                    max=30,
                    step=0.5,
                    unit_of_measurement="mi",
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Optional(
                CONF_INCIDENT_TYPES,
                default=list(options.get(CONF_INCIDENT_TYPES) or []),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=INCIDENT_TYPE_CHOICES,
                    multiple=True,
                    custom_value=True,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_WORK_ZONES_ENABLED,
                default=options.get(
                    CONF_WORK_ZONES_ENABLED, DEFAULT_WORK_ZONES_ENABLED
                ),
            ): BooleanSelector(),
            vol.Required(
                CONF_WORK_ZONE_RADIUS,
                default=options.get(CONF_WORK_ZONE_RADIUS, DEFAULT_WORK_ZONE_RADIUS),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0.5,
                    max=30,
                    step=0.5,
                    unit_of_measurement="mi",
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Optional(
                CONF_WORK_ZONE_TYPES,
                default=list(options.get(CONF_WORK_ZONE_TYPES) or []),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=WORK_ZONE_TYPE_CHOICES,
                    multiple=True,
                    custom_value=True,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
        }
    )


class OKCConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the OKC Services config flow."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialise the flow."""
        self._geocode: GeocodeResult | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect the service address and verify it against OKC data."""
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input[CONF_ADDRESS].strip()
            client = OKCClient(async_get_clientsession(self.hass))

            try:
                geocode = await client.geocode(address)
                # Confirm up front that the property is actually served, so the
                # user gets a clear error here rather than an empty calendar.
                await client.async_get_schedule(
                    geocode.latitude, geocode.longitude, TRASH_HORIZON_DAYS
                )
            except AddressNotFoundError:
                errors["base"] = "address_not_found"
            except OutsideServiceAreaError:
                errors["base"] = "outside_service_area"
            except OKCApiError:
                _LOGGER.exception("Error contacting OKC open data services")
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(
                    f"{geocode.latitude:.6f},{geocode.longitude:.6f}"
                )
                self._abort_if_unique_id_configured()
                self._geocode = geocode
                return await self.async_step_confirm()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user confirm the geocoder's interpretation of the address."""
        assert self._geocode is not None
        geocode = self._geocode

        if user_input is not None:
            return await self.async_step_options()

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders={
                "address": geocode.matched_address,
                "latitude": f"{geocode.latitude:.6f}",
                "longitude": f"{geocode.longitude:.6f}",
            },
        )

    async def async_step_options(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Offer the incident map options as part of initial setup."""
        assert self._geocode is not None
        geocode = self._geocode

        if user_input is not None:
            return self.async_create_entry(
                title=geocode.matched_address,
                data={
                    CONF_ADDRESS: geocode.matched_address,
                    CONF_MATCHED_ADDRESS: geocode.matched_address,
                    CONF_LATITUDE: geocode.latitude,
                    CONF_LONGITUDE: geocode.longitude,
                },
                options=user_input,
            )

        return self.async_show_form(
            step_id="options", data_schema=incident_options_schema({})
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OKCOptionsFlow:
        """Return the options flow."""
        return OKCOptionsFlow()


class OKCOptionsFlow(OptionsFlow):
    """Handle OKC Services options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage incident map options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=incident_options_schema(self.config_entry.options),
        )
