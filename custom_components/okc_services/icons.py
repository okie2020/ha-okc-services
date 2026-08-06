"""Map marker pictures for OKC emergency responses.

Home Assistant draws a geo_location marker as either the initials of the
entity name or, when the entity exposes one, its ``entity_picture``. There is
no way to hand the map an mdi icon, so each incident carries a small inline
SVG built here and served as a data URI.

Icon paths are taken verbatim from Material Design Icons (@mdi/svg 7.4.47),
which is Apache-2.0 licensed.
"""

from __future__ import annotations

import base64
from functools import lru_cache

# mdi:car-emergency
_CAR_EMERGENCY = (
    "M11 0V3H13V0H11M7.88 1.46L6.46 2.87L8.59 5L10 3.58L7.88 1.46M16.12 1.46L14 "
    "3.58L15.41 5L17.54 2.88L16.12 1.46M12 5A2 2 0 0 0 10 7V8H6.5C5.84 8 5.28 8.42 "
    "5.08 9L3 15V23A1 1 0 0 0 4 24H5A1 1 0 0 0 6 23V22H18V23A1 1 0 0 0 19 24H20A1 1 "
    "0 0 0 21 23V15L18.92 9C18.72 8.42 18.16 8 17.5 8H14V7A2 2 0 0 0 12 5M6.5 "
    "9.5H17.5L19 14H5L6.5 9.5M6.5 16A1.5 1.5 0 0 1 8 17.5A1.5 1.5 0 0 1 6.5 19A1.5 "
    "1.5 0 0 1 5 17.5A1.5 1.5 0 0 1 6.5 16M17.5 16A1.5 1.5 0 0 1 19 17.5A1.5 1.5 0 "
    "0 1 17.5 19A1.5 1.5 0 0 1 16 17.5A1.5 1.5 0 0 1 17.5 16Z"
)

# mdi:fire
_FIRE = (
    "M17.66 11.2C17.43 10.9 17.15 10.64 16.89 10.38C16.22 9.78 15.46 9.35 14.82 "
    "8.72C13.33 7.26 13 4.85 13.95 3C13 3.23 12.17 3.75 11.46 4.32C8.87 6.4 7.85 "
    "10.07 9.07 13.22C9.11 13.32 9.15 13.42 9.15 13.55C9.15 13.77 9 13.97 8.8 "
    "14.05C8.57 14.15 8.33 14.09 8.14 13.93C8.08 13.88 8.04 13.83 8 13.76C6.87 "
    "12.33 6.69 10.28 7.45 8.64C5.78 10 4.87 12.3 5 14.47C5.06 14.97 5.12 15.47 "
    "5.29 15.97C5.43 16.57 5.7 17.17 6 17.7C7.08 19.43 8.95 20.67 10.96 20.92C13.1 "
    "21.19 15.39 20.8 17.03 19.32C18.86 17.66 19.5 15 18.56 12.72L18.43 12.46C18.22 "
    "12 17.66 11.2 17.66 11.2M14.5 17.5C14.22 17.74 13.76 18 13.4 18.1C12.28 18.5 "
    "11.16 17.94 10.5 17.28C11.69 17 12.4 16.12 12.61 15.23C12.78 14.43 12.46 13.77 "
    "12.33 13C12.21 12.26 12.23 11.63 12.5 10.94C12.69 11.32 12.89 11.7 13.13 "
    "12C13.9 13 15.11 13.44 15.37 14.8C15.41 14.94 15.43 15.08 15.43 15.23C15.46 "
    "16.05 15.1 16.95 14.5 17.5H14.5Z"
)

# mdi:biohazard
_BIOHAZARD = (
    "M23,16.06C23,16.29 23,16.5 22.96,16.7C22.78,14.14 20.64,12.11 18,12.11C17.63,"
    "12.11 17.27,12.16 16.92,12.23C16.96,12.5 17,12.73 17,13C17,15.35 15.31,17.32 "
    "13.07,17.81C13.42,20.05 15.31,21.79 17.65,21.96C17.43,22 17.22,22 17,22C14.92,"
    "22 13.07,20.94 12,19.34C10.93,20.94 9.09,22 7,22C6.78,22 6.57,22 6.35,21.96C8.69,"
    "21.79 10.57,20.06 10.93,17.81C8.68,17.32 7,15.35 7,13C7,12.73 7.04,12.5 7.07,"
    "12.23C6.73,12.16 6.37,12.11 6,12.11C3.36,12.11 1.22,14.14 1.03,16.7C1,16.5 1,"
    "16.29 1,16.06C1,12.85 3.59,10.24 6.81,10.14C6.3,9.27 6,8.25 6,7.17C6,4.94 7.23,"
    "3 9.06,2C7.81,2.9 7,4.34 7,6C7,7.35 7.56,8.59 8.47,9.5C9.38,8.59 10.62,8.04 12,"
    "8.04C13.37,8.04 14.62,8.59 15.5,9.5C16.43,8.59 17,7.35 17,6C17,4.34 16.18,2.9 "
    "14.94,2C16.77,3 18,4.94 18,7.17C18,8.25 17.7,9.27 17.19,10.14C20.42,10.24 23,"
    "12.85 23,16.06M9.27,10.11C10.05,10.62 11,10.92 12,10.92C13,10.92 13.95,10.62 "
    "14.73,10.11C14,9.45 13.06,9.03 12,9.03C10.94,9.03 10,9.45 9.27,10.11M12,14.47C12"
    ".82,14.47 13.5,13.8 13.5,13A1.5,1.5 0 0,0 12,11.5A1.5,1.5 0 0,0 10.5,13C10.5,"
    "13.8 11.17,14.47 12,14.47M10.97,16.79C10.87,14.9 9.71,13.29 8.05,12.55C8.03,12.7 "
    "8,12.84 8,13C8,14.82 9.27,16.34 10.97,16.79M15.96,12.55C14.29,13.29 13.12,14.9 "
    "13,16.79C14.73,16.34 16,14.82 16,13C16,12.84 15.97,12.7 15.96,12.55Z"
)

# mdi:lifebuoy
_LIFEBUOY = (
    "M19.79,15.41C20.74,13.24 20.74,10.75 19.79,8.59L17.05,9.83C17.65,11.21 17.65,"
    "12.78 17.06,14.17L19.79,15.41M15.42,4.21C13.25,3.26 10.76,3.26 8.59,4.21L9.83,"
    "6.94C11.22,6.35 12.79,6.35 14.18,6.95L15.42,4.21M4.21,8.58C3.26,10.76 3.26,13.24 "
    "4.21,15.42L6.95,14.17C6.35,12.79 6.35,11.21 6.95,9.82L4.21,8.58M8.59,19.79C10.76,"
    "20.74 13.25,20.74 15.42,19.78L14.18,17.05C12.8,17.65 11.22,17.65 9.84,17.06L8.59,"
    "19.79M12,2A10,10 0 0,1 22,12A10,10 0 0,1 12,22A10,10 0 0,1 2,12A10,10 0 0,1 12,"
    "2M12,8A4,4 0 0,0 8,12A4,4 0 0,0 12,16A4,4 0 0,0 16,12A4,4 0 0,0 12,8Z"
)

# mdi:medical-bag
_MEDICAL_BAG = (
    "M10,3L8,5V7H5C3.85,7 3.12,8 3,9L2,19C1.88,20 2.54,21 4,21H20C21.46,21 22.12,20 "
    "22,19L21,9C20.88,8 20.06,7 19,7H16V5L14,3H10M10,5H14V7H10V5M11,10H13V13H16V15H13"
    "V18H11V15H8V13H11V10Z"
)

# mdi:alert-circle
_ALERT_CIRCLE = (
    "M13,13H11V7H13M13,17H11V15H13M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,"
    "0 22,12A10,10 0 0,0 12,2Z"
)

# Matched as substrings against Call_Type, most specific first, so
# "Fire: Elevator Emergency" lands on the fire icon and "Injury Accident" is
# tested before the broader "accident".
_ICON_RULES: tuple[tuple[str, str, str], ...] = (
    ("non-injury accident", _CAR_EMERGENCY, "#fb8c00"),
    ("injury accident", _CAR_EMERGENCY, "#e53935"),
    ("hazmat", _BIOHAZARD, "#43a047"),
    ("rescue", _LIFEBUOY, "#1e88e5"),
    ("medical", _MEDICAL_BAG, "#00897b"),
    ("fire", _FIRE, "#b71c1c"),
    ("accident", _CAR_EMERGENCY, "#fb8c00"),
)

_FALLBACK = (_ALERT_CIRCLE, "#757575")


@lru_cache(maxsize=32)
def incident_picture(call_type: str) -> str:
    """Return a data URI for an incident's map marker.

    Cached because the feed only ever holds a handful of distinct call types,
    and the marker is rebuilt on every coordinator refresh.
    """
    lowered = call_type.casefold()
    path, colour = _FALLBACK
    for needle, candidate_path, candidate_colour in _ICON_RULES:
        if needle in lowered:
            path, colour = candidate_path, candidate_colour
            break

    # The icon is scaled to 60% and centred, leaving a coloured ring around it
    # so the marker still reads as a marker at map zoom levels.
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        f'<circle cx="12" cy="12" r="12" fill="{colour}"/>'
        f'<g transform="translate(4.8 4.8) scale(0.6)">'
        f'<path d="{path}" fill="#ffffff"/></g></svg>'
    )
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"
