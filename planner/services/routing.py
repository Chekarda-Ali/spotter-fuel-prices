"""Routing providers. Exactly ONE HTTP call is made per trip request."""
from dataclasses import dataclass

import numpy as np
import requests
from django.conf import settings

from planner.exceptions import NoRouteError, RoutingError

METERS_PER_MILE = 1609.344
_session = requests.Session()  # connection reuse => faster repeated calls


@dataclass
class RawRoute:
    lats: np.ndarray
    lngs: np.ndarray
    distance_miles: float
    duration_hours: float


class OSRMRouter:
    """Free, keyless, fast. https://project-osrm.org (public demo server)."""

    def route(self, start, finish) -> RawRoute:
        cfg = settings.ROUTING
        url = f"{cfg['OSRM_URL']}/route/v1/driving/{start.lng},{start.lat};{finish.lng},{finish.lat}"
        try:
            resp = _session.get(url, params={"overview": "full", "geometries": "geojson",
                                             "steps": "false", "alternatives": "false"},
                                timeout=cfg["TIMEOUT_SECONDS"])
        except requests.RequestException as exc:
            raise RoutingError(f"Routing service unreachable: {exc}")
        if resp.status_code != 200:
            try:
                code = resp.json().get("code")
            except ValueError:
                code = None
            if code == "NoRoute":
                raise NoRouteError("No drivable route between these locations.")
            raise RoutingError(f"Routing service error (HTTP {resp.status_code}).")
        data = resp.json()
        if data.get("code") != "Ok" or not data.get("routes"):
            raise NoRouteError("No drivable route between these locations.")
        route = data["routes"][0]
        coords = np.asarray(route["geometry"]["coordinates"], dtype=float)  # [lng, lat]
        return RawRoute(coords[:, 1], coords[:, 0], route["distance"] / METERS_PER_MILE,
                        route["duration"] / 3600)


class ORSRouter:
    """OpenRouteService alternative (needs a free API key in ORS_API_KEY)."""

    URL = "https://api.openrouteservice.org/v2/directions/driving-hgv/geojson"

    def route(self, start, finish) -> RawRoute:
        cfg = settings.ROUTING
        if not cfg["ORS_API_KEY"]:
            raise RoutingError("ORS_API_KEY is not configured.", status=500)
        try:
            resp = _session.post(self.URL, json={"coordinates": [[start.lng, start.lat], [finish.lng, finish.lat]]},
                                 headers={"Authorization": cfg["ORS_API_KEY"]}, timeout=cfg["TIMEOUT_SECONDS"])
        except requests.RequestException as exc:
            raise RoutingError(f"Routing service unreachable: {exc}")
        if resp.status_code != 200:
            raise RoutingError(f"Routing service error (HTTP {resp.status_code}).")
        feat = resp.json()["features"][0]
        coords = np.asarray(feat["geometry"]["coordinates"], dtype=float)
        summary = feat["properties"]["summary"]
        return RawRoute(coords[:, 1], coords[:, 0], summary["distance"] / METERS_PER_MILE,
                        summary["duration"] / 3600)


def get_router():
    return {"osrm": OSRMRouter, "ors": ORSRouter}[settings.ROUTING["BACKEND"]]()
