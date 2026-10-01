from urllib.parse import urlencode

from django.urls import reverse
from django.views.generic import TemplateView
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .exceptions import PlannerError
from .serializers import RouteRequestSerializer
from .services.trip import plan_trip


class RoutePlanView(APIView):
    """GET /api/route/?start=Dallas,TX&finish=Seattle,WA   or   POST {"start":..,"finish":..}"""

    def get(self, request):
        return self._handle(request.query_params.dict())

    def post(self, request):
        return self._handle(request.data)

    def _handle(self, payload):
        ser = RouteRequestSerializer(data=payload)
        ser.is_valid(raise_exception=True)
        v = ser.validated_data
        try:
            result = plan_trip(
                v["start"], v["finish"],
                max_range=v.get("max_range_miles"), mpg=v.get("mpg"),
                start_fuel_miles=v["start_fuel_miles"], max_detour=v.get("max_detour_miles"),
            )
        except PlannerError as exc:
            return Response({"error": str(exc)}, status=exc.status)
        result["map_url"] = self._map_url(payload)
        return Response(result, status=status.HTTP_200_OK)

    def _map_url(self, payload) -> str:
        def label(x):
            return x if isinstance(x, str) else f"{x.get('lat')},{x.get('lng', x.get('lon'))}"
        q = urlencode({"start": label(payload["start"]), "finish": label(payload["finish"])})
        return f"{self.request.build_absolute_uri(reverse('route-map'))}?{q}"


class MapView(TemplateView):
    """Interactive Leaflet map that calls the JSON API above."""
    template_name = "planner/map.html"


class HealthView(APIView):
    def get(self, request):
        return Response({"status": "ok"})
