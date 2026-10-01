"""In-memory spatial index of stations.

The station table is small (~6.6k rows), so we load it ONCE per process into
numpy arrays. Per request we snap stations to the route with a KD-tree: O(log n)
per station, no per-request DB scan.
"""
from dataclasses import dataclass
from threading import Lock

import numpy as np
from scipy.spatial import cKDTree

from stations.models import Station

from .geo import chord_to_miles, miles_to_chord, to_unit_xyz


@dataclass
class Candidates:
    """Stations that lie within the corridor around the route."""
    rows: np.ndarray          # indices into the index arrays
    position_miles: np.ndarray  # distance along the route at the snapped point
    detour_miles: np.ndarray    # straight-line distance from the route


class StationIndex:
    def __init__(self):
        qs = list(Station.objects.values("id", "opis_id", "name", "address", "city", "state", "lat", "lng", "price"))
        self.meta = qs
        self.lat = np.array([s["lat"] for s in qs], dtype=float)
        self.lng = np.array([s["lng"] for s in qs], dtype=float)
        self.price = np.array([s["price"] for s in qs], dtype=float)
        self.xyz = to_unit_xyz(self.lat, self.lng) if len(qs) else np.empty((0, 3))
        self.mean_price = float(self.price.mean()) if len(qs) else 3.50

    def near_route(self, route_lats, route_lngs, route_cum, max_detour_miles: float) -> Candidates:
        if len(self.meta) == 0:
            return Candidates(np.array([], int), np.array([]), np.array([]))
        # cheap bounding-box prefilter (1 degree of latitude ~ 69 miles)
        pad = max_detour_miles / 69.0 + 0.2
        mask = ((self.lat >= route_lats.min() - pad) & (self.lat <= route_lats.max() + pad)
                & (self.lng >= route_lngs.min() - pad * 1.6) & (self.lng <= route_lngs.max() + pad * 1.6))
        rows = np.flatnonzero(mask)
        if rows.size == 0:
            return Candidates(rows, np.array([]), np.array([]))
        tree = cKDTree(to_unit_xyz(route_lats, route_lngs))
        chord, nearest = tree.query(self.xyz[rows], distance_upper_bound=miles_to_chord(max_detour_miles))
        ok = np.isfinite(chord)
        rows, chord, nearest = rows[ok], chord[ok], nearest[ok]
        return Candidates(rows, route_cum[nearest], chord_to_miles(chord))


_index: StationIndex | None = None
_lock = Lock()


def get_index() -> StationIndex:
    global _index
    if _index is None:
        with _lock:
            if _index is None:
                _index = StationIndex()
    return _index


def reset_index() -> None:
    """Drop the in-memory copy (tests / after reloading data)."""
    global _index
    _index = None
