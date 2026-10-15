import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
import django

django.setup()
from unittest.mock import patch
from django.test import SimpleTestCase, override_settings
from .service import resolve_city


@override_settings(ALLOWED_HOSTS=["testserver"])
class CityTests(SimpleTestCase):
    def test_short_query_does_not_call_provider(self):
        with patch("routing.views.search_cities") as search:
            self.assertEqual(self.client.get("/api/cities?q=c").json(), {"cities": []})
            search.assert_not_called()

    def test_search_returns_multiple_choices(self):
        choices = [
            {"name": "Springfield, Illinois, USA", "lat": 39.8, "lon": -89.6},
            {"name": "Springfield, Massachusetts, USA", "lat": 42.1, "lon": -72.5},
        ]
        with patch("routing.views.search_cities", return_value=choices):
            self.assertEqual(
                self.client.get("/api/cities?q=Springfield").json()["cities"], choices
            )

    def test_selected_coordinates_are_used_without_regeocoding(self):
        city = {"name": "Springfield, Massachusetts, USA", "lat": 42.1, "lon": -72.5}
        with patch("routing.service.geocode") as lookup:
            self.assertEqual(resolve_city(city["name"], city), city)
            lookup.assert_not_called()
        with self.assertRaises(ValueError):
            resolve_city("Other city", city)
        with self.assertRaises(ValueError):
            resolve_city(city["name"], {**city, "lat": float("nan")})
