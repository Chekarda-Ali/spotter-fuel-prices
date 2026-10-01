from unittest import mock

import pytest
from rest_framework.test import APIClient

from planner.tests.helpers import FakeRouter

URL = "/api/route/"


@pytest.fixture
def client(loaded_data):
    FakeRouter.calls = 0
    with mock.patch("planner.services.trip.get_router", lambda: FakeRouter()):
        yield APIClient()


def test_cross_country_route(client):
    r = client.post(URL, {"start": "Los Angeles, CA", "finish": "New York, NY"}, format="json")
    assert r.status_code == 200, r.content
    d = r.json()
    assert d["distance_miles"] > 2500
    assert len(d["fuel_stops"]) >= 5            # 500-mile range => several stops
    assert d["route"]["type"] == "LineString"
    assert all(s["detour_miles"] <= 10 for s in d["fuel_stops"])
    # money = sum of every purchase; gallons = distance / 10 mpg
    spent = sum(s["cost"] for s in d["fuel_stops"]) + (d["origin_fill"]["cost"] if d["origin_fill"] else 0)
    assert d["total_fuel_cost"] == pytest.approx(spent, abs=0.05)
    assert d["total_gallons"] == pytest.approx(d["distance_miles"] / 10, abs=0.1)
    # stops are in route order and never more than 500 miles apart
    marks = [s["mile_marker"] for s in d["fuel_stops"]]
    assert marks == sorted(marks)
    assert all(b - a <= 500.5 for a, b in zip([0] + marks, marks))


def test_only_one_external_call_and_cache(client):
    body = {"start": "Dallas, TX", "finish": "Denver, CO"}
    client.post(URL, body, format="json")
    r2 = client.post(URL, body, format="json")
    assert FakeRouter.calls == 1               # second request served from cache
    assert r2.json()["cached"] is True


def test_get_and_post_agree(client):
    a = client.get(URL, {"start": "Dallas, TX", "finish": "Denver, CO"}).json()
    b = client.post(URL, {"start": "Dallas, TX", "finish": "Denver, CO"}, format="json").json()
    assert a["total_fuel_cost"] == b["total_fuel_cost"]


@pytest.mark.parametrize("body", [
    {"start": "Dallas, TX"},
    {"start": "Dallas, TX", "finish": "Dallas, TX"},
    {"start": "Paris, France", "finish": "Denver, CO"},
    {"start": "51.5,-0.12", "finish": "Denver, CO"},
])
def test_validation_errors_are_400(client, body):
    assert client.post(URL, body, format="json").status_code == 400


def test_routing_failure_is_502(client):
    from planner.exceptions import RoutingError

    class Boom:
        def route(self, *a):
            raise RoutingError("down")

    with mock.patch("planner.services.trip.get_router", lambda: Boom()):
        r = client.post(URL, {"start": "Dallas, TX", "finish": "Denver, CO"}, format="json")
    assert r.status_code == 502 and "error" in r.json()


def test_map_page_renders(client):
    assert client.get("/map/").status_code == 200


def test_root_redirects_to_map(client):
    r = client.get("/")
    assert r.status_code == 302 and r["Location"].endswith("/map/")


def test_referrer_policy_allows_map_tiles(client):
    assert client.get("/map/")["Referrer-Policy"] == "strict-origin-when-cross-origin"