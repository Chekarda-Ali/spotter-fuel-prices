import pytest

from planner.exceptions import InfeasibleTripError
from planner.services.optimizer import plan_fuel_stops


def run(positions, prices, total, origin_price=4.0, rng=500, start_fuel=0.0):
    plan = plan_fuel_stops(positions, prices, total, origin_price, rng, start_fuel)
    return plan, sum(p.miles * p.price for p in plan.purchases) / 10


def test_short_trip_buys_only_at_origin():
    plan, cost = run([100], [3.0], 300, origin_price=4.0)
    # station is cheaper but mile 100: buy just enough to reach it, then the rest there
    assert [p.node for p in plan.purchases] == [0, 1]
    assert sum(p.miles for p in plan.purchases) == pytest.approx(300)


def test_total_miles_bought_equals_trip_length():
    plan, _ = run([200, 600, 1100], [3.5, 3.1, 3.4], 1500)
    assert sum(p.miles for p in plan.purchases) == pytest.approx(1500)


def test_prefers_cheaper_station_ahead_over_expensive_nearby():
    # origin $4.00, cheap $2.50 at mile 400 (reachable) -> buy only 400 miles at origin
    plan, _ = run([100, 400], [4.5, 2.5], 800, origin_price=4.0)
    assert plan.purchases[0].node == 0 and plan.purchases[0].miles == pytest.approx(400)
    assert plan.purchases[1].price == 2.5


def test_fills_tank_when_nothing_cheaper_in_reach():
    # everything ahead is pricier: fill fully at origin, hop to cheapest reachable
    plan, _ = run([300, 450], [5.0, 4.5], 900, origin_price=3.0)
    assert plan.purchases[0].miles == pytest.approx(500)
    assert plan.purchases[1].price == 4.5


def test_multi_stop_long_route():
    positions = [400, 800, 1200, 1600, 2000, 2400]
    plan, _ = run(positions, [3.4, 3.0, 3.6, 3.1, 3.7, 3.2], 2800)
    assert len(plan.purchases) >= 5
    assert sum(p.miles for p in plan.purchases) == pytest.approx(2800)


def test_gap_longer_than_range_is_infeasible():
    with pytest.raises(InfeasibleTripError):
        run([100, 900], [3.0, 3.0], 1000)


def test_start_fuel_reduces_purchases():
    plan, _ = run([], [], 400, origin_price=4.0, start_fuel=500)
    assert plan.purchases == []


def test_matches_bruteforce_dp():
    """Greedy cost equals an exhaustive DP on random instances."""
    import random
    for seed in range(200):
        rnd = random.Random(seed)
        total = rnd.choice([700, 1300, 2100])
        pos = sorted(rnd.sample(range(10, total, 10), rnd.randint(3, 12)))
        pr = [round(rnd.uniform(2.8, 4.5), 2) for _ in pos]
        try:
            _, greedy = run(pos, pr, total, origin_price=3.9)
        except InfeasibleTripError:
            continue
        assert greedy == pytest.approx(_dp(pos, pr, total, 3.9, 500), rel=1e-9)


def _dp(pos, pr, total, origin_price, rng, step=10):
    """Min cost via DP over (node, fuel in `step`-mile units)."""
    from functools import lru_cache
    nodes = [0] + list(pos) + [total]
    price = [origin_price] + list(pr) + [0.0]
    cap = rng // step

    @lru_cache(maxsize=None)
    def f(i, fuel):
        if i == len(nodes) - 1:
            return 0.0
        best = float("inf")
        for buy in range(0, cap - fuel + 1):
            if i + 1 < len(nodes):
                d = (nodes[i + 1] - nodes[i]) // step
                if fuel + buy < d:
                    continue
                best = min(best, buy * step * price[i] / 10 + f(i + 1, fuel + buy - d))
        return best

    return f(0, 0)


def test_min_saving_skips_pointless_micro_stops():
    # station at mile 100 is only 1 cent cheaper than the origin; the real bargain is at mile 450
    pos, pr = [100, 450], [3.99, 3.00]
    exact = plan_fuel_stops(pos, pr, 900, 4.00, 500)
    practical = plan_fuel_stops(pos, pr, 900, 4.00, 500, min_saving=0.03)
    assert 1 in [p.node for p in exact.purchases]            # exact optimum stops for 1 cent
    assert [p.node for p in practical.purchases] == [0, 2]   # practical plan skips it
