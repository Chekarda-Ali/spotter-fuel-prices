"""Orchestrates one trip request: locations -> route -> candidates -> plan -> response."""
import hashlib
import json

import numpy as np
from django.conf import settings
from django.core.cache import cache

from planner.exceptions import InfeasibleTripError

from .optimizer import plan_fuel_stops
from .routing import get_router
from .station_index import get_index
from .geo import resample_polyline


def _cache_key(start, finish, params) -> str:
    raw = json.dumps([round(start.lat, 3), round(start.lng, 3), round(finish.lat, 3),
                      round(finish.lng, 3), params], sort_keys=True)
    return "trip:" + hashlib.sha1(raw.encode()).hexdigest()


def plan_trip(start, finish, *, max_range=None, mpg=None, start_fuel_miles=0.0, max_detour=None) -> dict:
    cfg = settings.FUEL_PLANNER
    max_range = max_range or cfg["MAX_RANGE_MILES"]
    mpg = mpg or cfg["MPG"]
    max_detour = max_detour or cfg["MAX_DETOUR_MILES"]
    params = {"r": max_range, "mpg": mpg, "f": start_fuel_miles, "d": max_detour}

    key = _cache_key(start, finish, params)
    cached = cache.get(key)
    if cached is not None:
        return {**cached, "cached": True}

    # ---- the ONE external call -------------------------------------------
    raw = get_router().route(start, finish)

    lats, lngs, cum = resample_polyline(raw.lats, raw.lngs, raw.distance_miles, cfg["ROUTE_STEP_MILES"])
    total = float(cum[-1])

    index = get_index()

    # Search a narrow corridor first; if a gap longer than the range makes the
    # trip infeasible, widen the corridor step by step before giving up.
    corridors = [max_detour] + [w for w in (25.0, 50.0) if w > max_detour]
    for attempt, corridor in enumerate(corridors):
        cand = index.near_route(lats, lngs, cum, corridor)
        cand_prices = index.price[cand.rows]

        # assumed price at the origin: average of stations in the first N miles
        near_origin = cand.position_miles <= cfg["ORIGIN_PRICE_WINDOW_MILES"]
        if near_origin.any():
            origin_price = float(cand_prices[near_origin].mean())
        elif len(cand.rows):
            origin_price = float(cand_prices[np.argmin(cand.position_miles)])
        else:
            origin_price = index.mean_price
        try:
            plan = plan_fuel_stops(cand.position_miles, cand_prices, total, origin_price,
                                   max_range, start_fuel_miles, cfg["MIN_SAVING_PER_GALLON"],
                                   cfg["MIN_PURCHASE_GALLONS"] * mpg)
            break
        except InfeasibleTripError:
            if attempt == len(corridors) - 1:
                raise

    stops, origin_fill = [], None
    for p in plan.purchases:
        gallons = p.miles / mpg
        if p.node == 0:
            origin_fill = {"gallons": round(gallons, 2), "price_per_gallon": round(origin_price, 3),
                           "cost": round(gallons * origin_price, 2),
                           "note": "Assumed fill-up at the start at the average local price."}
            continue
        k = plan.order[p.node - 1]
        meta = index.meta[cand.rows[k]]
        stops.append({
            "order": len(stops) + 1,
            "name": meta["name"], "address": meta["address"], "city": meta["city"], "state": meta["state"],
            "lat": meta["lat"], "lng": meta["lng"],
            "price_per_gallon": round(meta["price"], 3),
            "mile_marker": round(float(cand.position_miles[k]), 1),
            "detour_miles": round(float(cand.detour_miles[k]), 1),
            "gallons": round(gallons, 2),
            "cost": round(gallons * meta["price"], 2),
        })

    total_gallons = sum(p.miles for p in plan.purchases) / mpg
    total_cost = sum(p.miles / mpg * p.price for p in plan.purchases)

    result = {
        "start": {"label": start.label, "lat": start.lat, "lng": start.lng},
        "finish": {"label": finish.label, "lat": finish.lat, "lng": finish.lng},
        "distance_miles": round(total, 1),
        "duration_hours": round(raw.duration_hours, 2),
        "vehicle": {"max_range_miles": max_range, "mpg": mpg},
        "fuel_stops": stops,
        "origin_fill": origin_fill,
        "total_gallons": round(total_gallons, 2),
        "total_fuel_cost": round(total_cost, 2),
        "stations_considered": int(len(cand.rows)),
        "search_corridor_miles": corridor,
        "route": {"type": "LineString",
                  "coordinates": np.column_stack([np.round(lngs, 5), np.round(lats, 5)]).tolist()},
    }
    cache.set(key, result, settings.ROUTE_CACHE_SECONDS)
    return {**result, "cached": False}