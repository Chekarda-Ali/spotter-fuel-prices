from django.urls import path
from django.views.generic import RedirectView

from . import views

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="route-map", permanent=False)),
    path("api/route/", views.RoutePlanView.as_view(), name="route-plan"),
    path("map/", views.MapView.as_view(), name="route-map"),
    path("health/", views.HealthView.as_view(), name="health"),
]