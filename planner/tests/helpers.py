import numpy as np

from planner.services.geo import haversine_miles
from planner.services.routing import RawRoute

ROAD_FACTOR = 1.15  # roads are ~15% longer than the straight line

# Rough interstate corridor LA -> NYC (I-40 / I-44 / I-70 / I-76) as (lat, lng)
LA_TO_NYC = [(34.05, -118.24), (35.2, -111.65), (35.08, -106.65), (35.22, -101.83), (35.47, -97.52),
             (38.63, -90.2), (39.77, -86.16), (39.96, -83.0), (40.44, -80.0), (40.71, -74.0)]


class FakeRouter:
    """Deterministic stand-in for OSRM: follows waypoints, no network."""
    calls = 0

    def route(self, start, finish):
        FakeRouter.calls += 1
        if abs(start.lat - 34.05) < 1 and abs(finish.lat - 40.71) < 1:
            pts = np.array(LA_TO_NYC)
        else:  # simple curved line
            t = np.linspace(0, 1, 50)
            pts = np.column_stack([start.lat + (finish.lat - start.lat) * t + 0.3 * np.sin(np.pi * t),
                                   start.lng + (finish.lng - start.lng) * t])
        straight = float(np.sum(haversine_miles(pts[:-1, 0], pts[:-1, 1], pts[1:, 0], pts[1:, 1])))
        miles = straight * ROAD_FACTOR
        return RawRoute(pts[:, 0], pts[:, 1], miles, miles / 55)
