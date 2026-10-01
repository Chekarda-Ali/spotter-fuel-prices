"""Cost-optimal refuelling plan (the classic "gas station" problem).

Model
-----
* The route is a line of length D. Stations sit at positions p_i with price c_i.
* The tank holds `max_range` miles of fuel. Fuel is bought in any quantity.
* We begin at position 0 (the *origin node*, which has an assumed price) and
  must reach D (a virtual *destination node* with price 0).

Greedy rule (provably optimal for this problem)
-----------------------------------------------
At station i with `fuel` miles in the tank:
  1. If a CHEAPER station j is reachable on a full tank (p_j - p_i <= range),
     buy only what is needed to get to the FIRST such j. Fuel bought here is
     never wasted, because j is cheaper and we arrive nearly empty.
  2. Otherwise fill the tank completely (nothing ahead in reach is cheaper),
     then drive to the cheapest station within reach (ties -> farthest, which
     means fewer stops).
  3. If nothing is reachable, the trip is infeasible (a gap longer than range).

Reach is found by binary search and the cheaper-station test is a vectorised
scan of the reachable window, so a plan costs roughly O(stops x window).
"""
from bisect import bisect_right
from dataclasses import dataclass

import numpy as np

from planner.exceptions import InfeasibleTripError

EPS = 1e-9


@dataclass
class Purchase:
    node: int          # 0 = origin, 1..n = candidate k-1 in input order (sorted by position)
    miles: float       # miles of range bought
    price: float       # $/gal


@dataclass
class Plan:
    order: np.ndarray            # candidate indices sorted by route position
    purchases: list[Purchase]    # chronological


def plan_fuel_stops(positions, prices, total_miles: float, origin_price: float,
                    max_range: float, start_fuel_miles: float = 0.0,
                    min_saving: float = 0.0, min_purchase_miles: float = 0.0) -> Plan:
    """`min_saving` ($/gal): a station only counts as "cheaper" if it saves at
    least this much. 0 gives the exact optimum; a few cents avoids silly
    one-gallon stops for sub-cent savings (cost impact is at most min_saving
    per gallon bought).

    `min_purchase_miles`: fill-ups smaller than this (in miles of range, i.e.
    gallons x mpg) are folded into the previous stop when the tank has room, so
    the driver never makes a stop just to buy a couple of gallons."""
    positions = np.asarray(positions, dtype=float)
    prices = np.asarray(prices, dtype=float)
    # sort candidates by position; equal positions -> cheaper first
    order = np.lexsort((prices, positions))
    pos = [0.0] + [min(float(positions[k]), total_miles) for k in order] + [float(total_miles)]
    price = np.array([float(origin_price)] + [float(prices[k]) for k in order] + [0.0])
    n = len(pos)
    dest = n - 1

    purchases: list[Purchase] = []
    i, fuel = 0, min(float(start_fuel_miles), max_range)
    while i < dest:
        hi = bisect_right(pos, pos[i] + max_range + EPS) - 1  # farthest node in reach
        if hi <= i:
            gap = pos[i + 1] - pos[i]
            raise InfeasibleTripError(
                f"No fuel station within {max_range:.0f} miles after mile {pos[i]:.0f} "
                f"(next one is {gap:.0f} miles away).")
        window = price[i + 1:hi + 1]
        cheaper = np.flatnonzero(window < price[i] - min_saving - EPS)
        if cheaper.size:                          # rule 1: first cheaper station in reach
            target = i + 1 + int(cheaper[0])
            buy = max(0.0, (pos[target] - pos[i]) - fuel)
        else:                                     # rule 2: fill up, go to cheapest in reach
            cheapest = window.min()
            target = i + 1 + int(np.flatnonzero(window <= cheapest + EPS)[-1])
            buy = max_range - fuel
        if buy > EPS:
            purchases.append(Purchase(node=i, miles=buy, price=float(price[i])))
        fuel += buy - (pos[target] - pos[i])
        i = target
    if min_purchase_miles > 0:
        purchases = _merge_small_purchases(purchases, pos, max_range, float(start_fuel_miles), min_purchase_miles,
                                         float(origin_price))
    return Plan(order=order, purchases=purchases)


def _merge_small_purchases(purchases: list[Purchase], pos: list[float], max_range: float,
                           start_fuel: float, min_miles: float, origin_price: float) -> list[Purchase]:
    """Remove stops whose fill-up is smaller than `min_miles`.

    A tiny purchase at stop b can be moved without disturbing the rest of the
    plan, because fuel is conserved (the tank level on arrival at every later
    stop stays the same). Three ways to move it, each only if physically valid:

      back    -> buy it at the previous stop    (needs room in the tank there)
      forward -> buy it at the next stop        (needs enough fuel to reach it)
      origin  -> buy it at the start fill-up    (for a tiny first stop at mile 0)

    The cheapest valid option wins; the smallest purchase is handled first.
    The origin purchase itself is never removed.
    """
    purchases = [Purchase(p.node, p.miles, p.price) for p in purchases]
    while True:
        after, level, last_pos = [], start_fuel, 0.0     # tank level right after each purchase
        for p in purchases:
            level = level - (pos[p.node] - last_pos) + p.miles
            after.append(level)
            last_pos = pos[p.node]

        best = None  # (miles, extra_cost, k, kind)
        for k, p in enumerate(purchases):
            if p.node == 0 or p.miles >= min_miles:
                continue
            if k > 0 and after[k - 1] + p.miles <= max_range + EPS:
                best = min(best or (1e18,), (p.miles, (purchases[k - 1].price - p.price) * p.miles, k, "back"))
            if k + 1 < len(purchases):
                prev_level = after[k - 1] if k > 0 else start_fuel
                prev_pos = pos[purchases[k - 1].node] if k > 0 else 0.0
                if prev_level - (pos[purchases[k + 1].node] - prev_pos) >= -EPS:
                    best = min(best or (1e18,), (p.miles, (purchases[k + 1].price - p.price) * p.miles, k, "fwd"))
            if k == 0 and pos[p.node] <= start_fuel + EPS and start_fuel + p.miles <= max_range + EPS:
                best = min(best or (1e18,), (p.miles, (origin_price - p.price) * p.miles, k, "origin"))
        if best is None:
            return purchases

        _, _, k, kind = best
        if kind == "back":
            purchases[k - 1].miles += purchases[k].miles
            del purchases[k]
        elif kind == "fwd":
            purchases[k + 1].miles += purchases[k].miles
            del purchases[k]
        else:
            purchases[k] = Purchase(node=0, miles=purchases[k].miles, price=origin_price)