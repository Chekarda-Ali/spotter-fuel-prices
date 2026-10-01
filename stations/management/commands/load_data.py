"""Load the pre-geocoded stations and the city gazetteer into the database.

    python manage.py load_data

Idempotent: tables are replaced, so it is safe to re-run.
"""
import csv
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from stations.models import City, Station


class Command(BaseCommand):
    help = "Load data/stations.csv and data/us_cities.csv"

    def add_arguments(self, parser):
        parser.add_argument("--data-dir", default=str(Path(settings.BASE_DIR) / "data"))

    @transaction.atomic
    def handle(self, *args, **opts):
        data_dir = Path(opts["data_dir"])

        with open(data_dir / "stations.csv", newline="", encoding="utf-8") as fh:
            stations = [
                Station(opis_id=int(r["opis_id"]), name=r["name"], address=r["address"], city=r["city"],
                        state=r["state"], lat=float(r["lat"]), lng=float(r["lng"]), price=float(r["price"]))
                for r in csv.DictReader(fh)
            ]
        Station.objects.all().delete()
        Station.objects.bulk_create(stations, batch_size=2000)

        with open(data_dir / "us_cities.csv", newline="", encoding="utf-8") as fh:
            cities = [
                City(name=r["city"], name_norm=r["name_norm"], state=r["state"],
                     lat=float(r["lat"]), lng=float(r["lng"]))
                for r in csv.DictReader(fh)
            ]
        City.objects.all().delete()
        City.objects.bulk_create(cities, batch_size=5000)

        self.stdout.write(self.style.SUCCESS(f"Loaded {len(stations)} stations and {len(cities)} cities."))
