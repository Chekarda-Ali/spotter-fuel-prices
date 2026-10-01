from django.db import models


class Station(models.Model):
    """A truck stop with its (lowest known) diesel retail price."""

    opis_id = models.PositiveIntegerField(unique=True)
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2)
    lat = models.FloatField()
    lng = models.FloatField()
    price = models.FloatField(help_text="USD per gallon")

    class Meta:
        indexes = [models.Index(fields=["lat", "lng"]), models.Index(fields=["price"])]

    def __str__(self) -> str:
        return f"{self.name} ({self.city}, {self.state}) ${self.price:.3f}"


class City(models.Model):
    """Offline gazetteer used to resolve 'City, ST' inputs without any API call."""

    name = models.CharField(max_length=120)
    name_norm = models.CharField(max_length=120)
    state = models.CharField(max_length=2)
    lat = models.FloatField()
    lng = models.FloatField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["name_norm", "state"], name="uniq_city_state")]
        verbose_name_plural = "cities"

    def __str__(self) -> str:
        return f"{self.name}, {self.state}"
