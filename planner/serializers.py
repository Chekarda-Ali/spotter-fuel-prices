from rest_framework import serializers

from .exceptions import LocationError
from .services.locations import parse_location


class LocationField(serializers.Field):
    """Accepts "City, ST", "lat,lng" or {"lat":..,"lng":..}; yields a Location."""

    def to_internal_value(self, data):
        try:
            return parse_location(data, self.field_name)
        except LocationError as exc:
            raise serializers.ValidationError(str(exc))

    def to_representation(self, value):
        return value.label


class RouteRequestSerializer(serializers.Serializer):
    start = LocationField()
    finish = LocationField()
    max_range_miles = serializers.FloatField(required=False, min_value=50, max_value=2000)
    mpg = serializers.FloatField(required=False, min_value=1, max_value=100)
    start_fuel_miles = serializers.FloatField(required=False, min_value=0, default=0.0)
    max_detour_miles = serializers.FloatField(required=False, min_value=0.5, max_value=50)

    def validate(self, attrs):
        a, b = attrs["start"], attrs["finish"]
        if abs(a.lat - b.lat) < 1e-4 and abs(a.lng - b.lng) < 1e-4:
            raise serializers.ValidationError("start and finish must be different places.")
        return attrs
