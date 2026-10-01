# Fuel Route Planner (Django API)

Give it a start and a finish inside the USA. It returns the driving route, the
**cheapest places to refuel** along it (500-mile range), and the **total fuel
cost** at 10 mpg.

* Django 6.1 (latest stable) + Django REST Framework
* **One** external routing call per request (OSRM, free, no key). Repeats are served from cache.
* Fuel stations are geocoded **once, offline**, and held in an in-memory KD-tree. No geocoding API is ever called.
* Typical response time: **5-50 ms** (a few hundred ms on the very first request after boot).

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate     # Python 3.12+ (Django 6 requirement)
pip install -r requirements.txt
python manage.py migrate
python manage.py load_data          # loads 6,614 stations + 29,738 cities (~3 s)
python manage.py runserver
```

Open **http://127.0.0.1:8000/map/** for the interactive map, or call the API:

```bash
curl -X POST http://127.0.0.1:8000/api/route/ \
  -H "Content-Type: application/json" \
  -d '{"start": "Los Angeles, CA", "finish": "New York, NY"}'
```

Import `postman_collection.json` into Postman for ready-made requests.
Tests: `pip install -r requirements-dev.txt && pytest`

## API

`POST /api/route/` (or `GET /api/route/?start=...&finish=...`)

| field | required | notes |
|---|---|---|
| `start`, `finish` | yes | `"Dallas, TX"` / `"Dallas, Texas"` / `"32.78,-96.80"` / `{"lat":..,"lng":..}` |
| `max_range_miles` | no | default 500 |
| `mpg` | no | default 10 |
| `start_fuel_miles` | no | range already in the tank at departure, default 0 |
| `max_detour_miles` | no | how far off the route a station may be, default 10 |

Response (abridged):

```json
{
  "start": {"label": "Dallas, TX", "lat": 32.78, "lng": -96.8},
  "finish": {"label": "Denver, CO", "lat": 39.74, "lng": -104.98},
  "distance_miles": 755.5,
  "duration_hours": 13.7,
  "vehicle": {"max_range_miles": 500.0, "mpg": 10.0},
  "fuel_stops": [
    {"order": 1, "name": "ALLSUPS #2476", "city": "Elk City", "state": "OK",
     "lat": 35.4, "lng": -99.4, "price_per_gallon": 2.931, "mile_marker": 258.1,
     "detour_miles": 1.4, "gallons": 22.9, "cost": 67.12}
  ],
  "origin_fill": {"gallons": 50.0, "price_per_gallon": 2.864, "cost": 143.2, "note": "..."},
  "total_gallons": 75.55,
  "total_fuel_cost": 217.98,
  "route": {"type": "LineString", "coordinates": [[-96.8, 32.78], "..."]},
  "map_url": "http://127.0.0.1:8000/map/?start=Dallas,+TX&finish=Denver,+CO",
  "cached": false
}
```

`route` is GeoJSON, so it drops straight into Leaflet / Mapbox / geojson.io. `map_url` opens it rendered.

Errors are JSON: `400` bad input, `422` no drivable route / fuel gap longer than the range, `502` routing service down.

## How it works

```
request ─► parse locations (offline) ─► ONE OSRM call ─► resample route to 0.5-mile points
        ─► KD-tree: stations within 10 mi of the route + their mile marker
        ─► greedy optimiser ─► JSON
```

1. **Offline data** (`scripts/build_datasets.py`, already run): the CSV had no coordinates, so city+state is joined to a free US gazetteer. Canadian rows are dropped; duplicate truckstop IDs are collapsed to their lowest price.
2. **Station snapping** (`planner/services/station_index.py`): stations are loaded once into numpy arrays; a `scipy` KD-tree finds each station's nearest route point (its **mile marker**) and its distance from the route.
3. **Optimiser** (`planner/services/optimizer.py`): the classic gas-station greedy. At each stop, if a cheaper station is reachable on a full tank, buy only enough to reach it; otherwise fill up and hop to the cheapest station in range. It is checked in the tests against an exhaustive DP on 200 random instances.
4. **Cost**: `gallons = miles / mpg`, summed price x gallons per purchase.

## Assumptions (please read)

* **Start-of-trip fuel.** The vehicle begins with an empty tank *at a fuel stop*, bought at the average price of stations in the first 50 miles (`origin_fill`). This makes `total_fuel_cost` always equal the full cost of the trip's fuel (`distance / mpg` gallons). Pass `start_fuel_miles` to begin with fuel on board.
* **Station coordinates are city-level.** The CSV only has highway exits, so a station's position is its city's centroid. Hence a 10-mile search corridor (configurable). If a gap longer than the range would make the trip impossible, the corridor automatically widens to 25 then 50 miles before returning an error.
* **Duplicate truckstop IDs** keep the lowest listed price.
* **Minimum saving.** A station only counts as "cheaper" if it saves at least $0.03/gal (`MIN_SAVING_PER_GALLON`), avoiding one-gallon stops for sub-cent savings. Set to `0` for the mathematically exact optimum.
* **Detour distance** is not charged as extra fuel.
* Only the contiguous USA is supported (stations exist only there).

## Configuration

Environment variables (see `.env.example`): `ROUTING_BACKEND` (`osrm` | `ors`), `ORS_API_KEY`, `MAX_RANGE_MILES`, `MPG`, `MAX_DETOUR_MILES`, `MIN_SAVING_PER_GALLON`, `ROUTE_CACHE_SECONDS`, `POSTGRES_*` (SQLite otherwise).
The public OSRM demo server is fine for evaluation; for production, self-host OSRM or use ORS.

## Layout

```
config/            settings, urls
stations/          Station + City models, `load_data` command
planner/
  services/        geo, locations, routing, station_index, optimizer, trip
  views.py         API + map page         templates/planner/map.html
  tests/           optimizer, locations, API (routing mocked)
scripts/           one-off dataset builder
data/              stations.csv (geocoded), us_cities.csv
```
