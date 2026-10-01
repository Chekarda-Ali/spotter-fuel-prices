# Fuel Route Planner

This is my solution to the Spotter backend assessment. You give the API a start and a finish inside the USA, and it returns the driving route, the places to stop for fuel, and what the fuel will cost. The vehicle can go 500 miles on a tank and does 10 miles per gallon.

It's built with Django 6.1 and Django REST Framework. The route comes from the free public OSRM server, and each request makes one call to it.

## Running it

You need Python 3.12 or newer, because Django 6 requires it.

```bash
python -m venv .venv
source .venv/bin/activate        # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py load_data
python manage.py runserver
```

`load_data` puts the stations and a list of US cities into the database. It takes a few seconds.

After that, http://127.0.0.1:8000/map/ shows a map with the route and the fuel stops. There is also a `postman_collection.json` in the repo with a few ready-made requests.

## Using the API

`POST /api/route/` with a JSON body (a GET with `?start=...&finish=...` works too):

```bash
curl -X POST http://127.0.0.1:8000/api/route/ \
  -H "Content-Type: application/json" \
  -d '{"start": "Los Angeles, CA", "finish": "New York, NY"}'
```

`start` and `finish` can be `"Dallas, TX"`, `"Dallas, Texas"`, `"32.78,-96.80"` or `{"lat": 32.78, "lng": -96.80}`. City names are looked up in a local table, so they don't cost an extra API call. There are also optional fields: `max_range_miles`, `mpg`, `start_fuel_miles` and `max_detour_miles`.

The response looks like this (shortened):

```json
{
  "distance_miles": 755.5,
  "fuel_stops": [
    {"order": 1, "name": "ALLSUPS #2476", "city": "Elk City", "state": "OK",
     "price_per_gallon": 2.931, "mile_marker": 258.1, "detour_miles": 1.4,
     "gallons": 22.9, "cost": 67.12}
  ],
  "origin_fill": {"gallons": 50.0, "price_per_gallon": 2.864, "cost": 143.2},
  "total_gallons": 75.55,
  "total_fuel_cost": 217.98,
  "route": {"type": "LineString", "coordinates": [[-96.8, 32.78], "..."]},
  "map_url": "http://127.0.0.1:8000/map/?start=Dallas,+TX&finish=Denver,+CO",
  "cached": false
}
```

The route is GeoJSON, and `map_url` opens it on the map page. Errors come back as JSON: 400 for bad input, 422 if there is no drivable route or a gap between stations is longer than the range, and 502 if the routing service is down.

## How it works

The CSV from the assessment has no coordinates, and I didn't want to geocode thousands of stations through an API. So I matched each station's city and state against a free list of US cities (kelvins/US-Cities-Database) and saved the result in `data/stations.csv`. `scripts/build_datasets.py` does this, and I've already run it. I dropped the Canadian rows, and when the same truckstop ID appeared several times with different prices I kept the lowest.

For each request:

1. One call to OSRM returns the route.
2. I resample the route to a point every half mile and use a KD-tree (scipy) to find the stations within 10 miles of it. Each one gets a mile marker, meaning how far along the route it is.
3. The planner chooses where to buy fuel.

The planner works like this. At a station, if there is a cheaper station within 500 miles, buy only enough fuel to reach it. If there isn't, fill the tank and drive to the cheapest station in range. In the tests I compare it to a brute-force solver on 200 random trips, and the costs match when my two practical rules below are turned off.

Results are cached by start and finish, so asking for the same trip again doesn't call OSRM.

## Assumptions

- **Start of the trip.** The vehicle starts with an empty tank and fills up at the start, at the average price of the stations in the first 50 miles. It shows up as `origin_fill`. I did this so the total cost covers all the fuel for the trip. If you want the tank to start with fuel in it, pass `start_fuel_miles`.
- **Station positions are approximate.** The CSV only has highway exits, so I use the city's centre as the station's location. That's why stations are accepted up to 10 miles from the route. If the trip would be impossible because of a gap, the search widens to 25 and then 50 miles.
- **Minimum saving.** A station only counts as cheaper if it saves at least $0.03 a gallon (`MIN_SAVING_PER_GALLON`). Without this the planner makes stops to save a fraction of a cent.
- **Minimum fill-up.** A stop doesn't buy fewer than 10 gallons (`MIN_PURCHASE_GALLONS`). A smaller purchase is moved to a neighbouring stop when the tank allows it. On a long trip like LA to New York this removed about a third of the stops and added well under 1% to the cost. Set either of these two settings to 0 to turn it off.
- The extra distance of a detour off the route isn't added to the fuel cost.
- Only the contiguous US is supported, since that's where the stations are.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

There are 33 tests covering the planner, the location parsing and the API. The OSRM call is mocked, so they run without internet.

## Settings

These are environment variables, and all of them have defaults: `ROUTING_BACKEND` (`osrm` or `ors`), `ORS_API_KEY`, `MAX_RANGE_MILES`, `MPG`, `MAX_DETOUR_MILES`, `MIN_SAVING_PER_GALLON`, `MIN_PURCHASE_GALLONS`, `ROUTE_CACHE_SECONDS`. If `POSTGRES_DB` is set it uses PostgreSQL, otherwise SQLite.

The public OSRM server is fine for this assessment. I wouldn't use it in production.

## What I would do next

- Use real coordinates for each exit instead of the city centre.
- Add the cost of detours to the fuel cost.
- Use Redis for the cache, so it's shared between workers.
- Run my own OSRM instance.

## Layout

```
config/          settings and urls
stations/        Station and City models, the load_data command
planner/
  services/      geo, locations, routing, station_index, optimizer, trip
  views.py       the API and the map page
  tests/
scripts/         the one-off script that built the data files
data/            stations.csv, us_cities.csv
```