# OKC Services — Home Assistant integration

A custom Home Assistant integration for City of Oklahoma City residents. Enter your
home address once and it will:

- resolve your **trash**, **recycling** and **bulky waste** collection zones,
- sync upcoming pickups into a **Home Assistant calendar** entity,
- expose **next pickup / days until pickup** sensors for each service,
- plot **live fire and police emergency responses** (crashes, fire calls) on the
  Home Assistant **map**.

All data comes from the [City of Oklahoma City open data portal](https://data.okc.gov/).
No API key or account is required.

## Installation

### HACS (recommended)

1. In Home Assistant go to **HACS → ⋮ → Custom repositories**.
2. Add `https://github.com/okie2020/ha-okc-services` with type **Integration**.
3. Find **OKC Services** in the HACS list and click **Download**.
4. Restart Home Assistant.

### Manual

1. Copy the `custom_components/okc_services` folder into your Home Assistant
   `config/custom_components/` directory, so you end up with
   `config/custom_components/okc_services/manifest.json`.
2. Restart Home Assistant.

### Configuration

1. Go to **Settings → Devices & services → Add integration** and search for
   **OKC Services**.
2. Enter your street address (for example `200 N Walker Ave, Oklahoma City, OK 73102`)
   and confirm the matched address on the next screen.

Your address is geocoded once, at setup, by the public ArcGIS World Geocoding
Service. Only the resulting coordinates are stored in your config entry, and
they never leave your Home Assistant instance except as the point-in-polygon
query sent to the City's public map services.

If the address is outside every OKC collection zone, setup stops with a clear error
rather than creating an empty calendar — service there is likely provided by another
municipality or a private hauler.

## Entities

One device is created per address, with these entities:

| Entity | Description |
| --- | --- |
| `calendar.<address>_collection_schedule` | All-day events for every upcoming pickup |
| `sensor.<address>_next_trash_pickup` | Date of next trash pickup |
| `sensor.<address>_next_recycling_pickup` | Date of next recycling pickup |
| `sensor.<address>_next_bulky_waste_pickup` | Date of next bulky waste pickup |
| `sensor.<address>_trash_pickup_in` | Whole days until trash pickup |
| `sensor.<address>_recycling_pickup_in` | Whole days until recycling pickup |
| `sensor.<address>_bulky_waste_pickup_in` | Whole days until bulky waste pickup |
| `sensor.<address>_nearby_emergency_responses` | Count of active incidents in radius |
| `geo_location.*` | One transient marker per active incident |

Each pickup sensor carries `route`, `pickup_day` and `service_provider` attributes.

> Exact entity IDs are derived from the matched address. Check
> **Developer tools → States** after setup to get yours.

## Options

**Settings → Devices & services → OKC Services → Configure**

- **Show emergency responses on the map** — turn the incident feed on or off.
- **Radius around your home** — default 5 km.
- **Only show these call types** — leave empty for everything. Matching is partial,
  so `Fire` also matches `Fire: Elevator Emergency`, and `Accident` matches both
  `Injury Accident` and `Non-Injury Accident`.

## Dashboard

Map with live incidents:

```yaml
type: map
geo_location_sources:
  - okc_emergency
entities:
  - zone.home
hours_to_show: 0
```

Collection calendar:

```yaml
type: calendar
initial_view: dayGridMonth
entities:
  - calendar.okc_collection_schedule
```

At-a-glance next pickups:

```yaml
type: entities
title: Waste collection
entities:
  - entity: sensor.okc_next_trash_pickup
    name: Trash
  - entity: sensor.okc_next_recycling_pickup
    name: Recycling
  - entity: sensor.okc_next_bulky_waste_pickup
    name: Bulky waste
```

## Example automation

Remind yourself the evening before a pickup:

```yaml
automation:
  - alias: "Take the bins out"
    triggers:
      - trigger: time
        at: "19:00:00"
    conditions:
      - condition: template
        value_template: >
          {{ states('sensor.okc_trash_pickup_in') | int(-1) == 1
             or states('sensor.okc_recycling_pickup_in') | int(-1) == 1 }}
    actions:
      - action: notify.mobile_app
        data:
          message: >
            Tomorrow:
            {% if states('sensor.okc_trash_pickup_in') | int(-1) == 1 %}trash{% endif %}
            {% if states('sensor.okc_recycling_pickup_in') | int(-1) == 1 %}recycling{% endif %}
```

## How it works

| Data | Source layer |
| --- | --- |
| Address → coordinates | ArcGIS World Geocoding Service (anonymous) |
| Trash zone | `OpenData/Utilities` layer 1 — `ROUTE`, `PICKUPDAY` |
| Bulky waste zone | `OpenData/Utilities` layer 2 |
| Recycle zone | `OpenData/Utilities` layer 3 |
| Bulky waste dates | `OpenData/Utilities` layer 10 — joined on `RouteNumber` |
| Recycling dates | `OpenData/Utilities` layer 11 — joined on `MeterReadingUnit` |
| Emergency responses | `OpenData/Public_Safety` layer 0 |

Your coordinates are matched against the zone polygons with a point-in-polygon
query. Recycling and bulky waste have published date tables that the integration
joins on the route; trash has no date table because it is a simple weekly service,
so those pickups are generated from the zone's `PICKUPDAY` weekday.

Schedules refresh every 6 hours; the incident feed polls every 5 minutes.

### Endpoint note

The integration talks to the ArcGIS Online proxy
(`utility.arcgis.com/usrsvcs/servers/<item id>/...`) rather than `gis.okc.gov`
directly. The direct host sits behind a bot-mitigation WAF that rejects
non-browser HTTP clients, so it is not usable from inside Home Assistant. The
`<item id>` segment is the public ArcGIS Online item id of each dataset, listed
in `const.py`.

## Caveats

- The City notes that published schedules can shift because of weather or holidays.
  This integration reports what the City publishes; it does not model holiday slips.
- The emergency response feed contains only **currently active** calls. Incidents
  disappear from the map when the City clears them, and there is no history.
- Incident coordinates are block/intersection level, as published.

## Attribution

Data provided by the City of Oklahoma City open data portal. Verify anything
critical against [My Trash Day](https://www.okc.gov/Services/Water-Trash-Recycling/Trash-Services/My-Trash-Day).
