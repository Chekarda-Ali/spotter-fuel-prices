"""Turn user input into coordinates WITHOUT calling any external API.

Accepted forms for `start` / `finish`:
    {"lat": 34.05, "lng": -118.24}          (also "lon" / "latitude" / "longitude")
    "34.05,-118.24"
    "Los Angeles, CA"   or   "Los Angeles, California"
"""
import re
from dataclasses import dataclass

from planner.exceptions import LocationError
from stations.models import City

# Stations exist for the contiguous US only; reject anything clearly outside it.
US_BOUNDS = {"lat": (24.0, 49.6), "lng": (-125.0, -66.5)}

STATE_NAMES = {
    "alabama": "AL", "arizona": "AZ", "arkansas": "AR", "california": "CA", "colorado": "CO",
    "connecticut": "CT", "delaware": "DE", "florida": "FL", "georgia": "GA", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS", "kentucky": "KY",
    "louisiana": "LA", "maine": "ME", "maryland": "MD", "massachusetts": "MA", "michigan": "MI",
    "minnesota": "MN", "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE",
    "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
    "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC", "south dakota": "SD",
    "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT", "virginia": "VA",
    "washington": "WA", "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
    "district of columbia": "DC",
}
STATE_CODES = set(STATE_NAMES.values())
_LATLNG = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*[,;\s]\s*(-?\d+(?:\.\d+)?)\s*$")


@dataclass(frozen=True)
class Location:
    lat: float
    lng: float
    label: str


def normalize_city(name: str) -> str:
    """Must mirror scripts/build_datasets.norm()."""
    s = name.lower().replace(".", "").strip()
    s = re.sub(r"^(saint|st)\b", "st", s)
    s = re.sub(r"^(fort|ft)\b", "fort", s)
    s = re.sub(r"^(mount|mt)\b", "mount", s)
    return re.sub(r"[^a-z0-9 ]", "", s)


def _check_bounds(lat: float, lng: float, what: str) -> None:
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise LocationError(f"'{what}' has invalid coordinates.")
    if not (US_BOUNDS["lat"][0] <= lat <= US_BOUNDS["lat"][1]
            and US_BOUNDS["lng"][0] <= lng <= US_BOUNDS["lng"][1]):
        raise LocationError(f"'{what}' is outside the supported area (contiguous USA).")


def parse_location(value, what: str = "location") -> Location:
    if isinstance(value, dict):
        lat = value.get("lat", value.get("latitude"))
        lng = value.get("lng", value.get("lon", value.get("longitude")))
        try:
            lat, lng = float(lat), float(lng)
        except (TypeError, ValueError):
            raise LocationError(f"'{what}' object needs numeric lat and lng.")
        _check_bounds(lat, lng, what)
        return Location(lat, lng, f"{lat:.5f}, {lng:.5f}")

    if not isinstance(value, str) or not value.strip():
        raise LocationError(f"'{what}' is required.")

    m = _LATLNG.match(value)
    if m:
        lat, lng = float(m.group(1)), float(m.group(2))
        _check_bounds(lat, lng, what)
        return Location(lat, lng, f"{lat:.5f}, {lng:.5f}")

    if "," not in value:
        raise LocationError(f"'{what}': use 'City, ST' (e.g. 'Dallas, TX') or 'lat,lng'.")
    city_part, state_part = (p.strip() for p in value.rsplit(",", 1))
    state = state_part.upper() if state_part.upper() in STATE_CODES else STATE_NAMES.get(state_part.lower())
    if not state:
        raise LocationError(f"'{what}': unknown US state '{state_part}'.")
    city = City.objects.filter(name_norm=normalize_city(city_part), state=state).first()
    if city is None:
        raise LocationError(f"'{what}': city '{city_part}, {state}' not found. Try 'lat,lng' instead.")
    _check_bounds(city.lat, city.lng, what)
    return Location(city.lat, city.lng, f"{city.name}, {city.state}")
