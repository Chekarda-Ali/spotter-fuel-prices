import pytest
from django.core.cache import cache
from django.core.management import call_command


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    """Load the dataset once per test session instead of once per test."""
    with django_db_blocker.unblock():
        call_command("load_data", verbosity=0)


@pytest.fixture
def loaded_data(db):
    from planner.services.station_index import reset_index
    reset_index()
    cache.clear()
    yield
    reset_index()
