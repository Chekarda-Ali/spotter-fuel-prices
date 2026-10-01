import pytest

from planner.exceptions import LocationError
from planner.services.locations import parse_location


@pytest.mark.django_db
def test_city_state_resolves_offline(loaded_data):
    loc = parse_location("Dallas, TX", "start")
    assert 32 < loc.lat < 33.5 and -97.5 < loc.lng < -96
    assert parse_location("dallas, texas").label == "Dallas, TX"


def test_latlng_forms():
    assert parse_location("34.05,-118.24").lat == 34.05
    assert parse_location({"lat": 40.7, "lng": -74.0}).lng == -74.0


@pytest.mark.parametrize("bad", ["", "Dallas", "51.5,-0.12", "Atlantis, ZZ", {"lat": "x"}, 5])
def test_bad_inputs_rejected(bad, loaded_data):
    with pytest.raises(LocationError):
        parse_location(bad)
