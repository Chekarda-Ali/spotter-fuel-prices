"""Small, vectorised geometry helpers (all distances in miles)."""
import numpy as np

EARTH_RADIUS_MILES = 3958.7613


def haversine_miles(lat1, lng1, lat2, lng2):
    lat1, lng1, lat2, lng2 = map(np.radians, (lat1, lng1, lat2, lng2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lng2 - lng1) / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * np.arcsin(np.sqrt(a))


def cumulative_miles(lats: np.ndarray, lngs: np.ndarray) -> np.ndarray:
    seg = haversine_miles(lats[:-1], lngs[:-1], lats[1:], lngs[1:])
    return np.concatenate([[0.0], np.cumsum(seg)])


def resample_polyline(lats, lngs, total_miles: float, step_miles: float):
    """Resample a polyline to ~uniform spacing along its length.

    OSRM returns thousands of irregular vertices (dense in cities, sparse on
    straight highway). Uniform spacing gives (a) a bounded payload and (b) a
    matching resolution of at most step/2 miles when snapping stations.
    The cumulative distance is rescaled so the last point equals the routing
    engine's own road distance.
    """
    lats = np.asarray(lats, dtype=float)
    lngs = np.asarray(lngs, dtype=float)
    raw = cumulative_miles(lats, lngs)
    if raw[-1] <= 0:
        return lats[:1], lngs[:1], np.array([0.0])
    n = max(2, int(np.ceil(raw[-1] / step_miles)) + 1)
    grid = np.linspace(0.0, raw[-1], n)
    new_lats = np.interp(grid, raw, lats)
    new_lngs = np.interp(grid, raw, lngs)
    cum = grid * (total_miles / raw[-1])
    return new_lats, new_lngs, cum


def to_unit_xyz(lats, lngs) -> np.ndarray:
    lat, lng = np.radians(lats), np.radians(lngs)
    return np.column_stack([np.cos(lat) * np.cos(lng), np.cos(lat) * np.sin(lng), np.sin(lat)])


def chord_to_miles(chord):
    return 2 * EARTH_RADIUS_MILES * np.arcsin(np.clip(np.asarray(chord) / 2, 0, 1))


def miles_to_chord(miles: float) -> float:
    return 2 * np.sin(miles / (2 * EARTH_RADIUS_MILES))
