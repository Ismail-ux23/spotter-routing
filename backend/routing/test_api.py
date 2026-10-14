import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
import django

django.setup()
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
import requests
from django.test import Client, override_settings, SimpleTestCase
from .service import plan, sample


@override_settings(ALLOWED_HOSTS=["testserver"])
class ApiTests(SimpleTestCase):
    def setUp(self):
        self.client = Client()

    def test_health(self):
        self.assertEqual(self.client.get("/api/health").json(), {"status": "ok"})

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get("/api/routes").status_code, 405)

    def test_content_type(self):
        self.assertEqual(
            self.client.post(
                "/api/routes", data="x", content_type="text/plain"
            ).status_code,
            415,
        )

    def test_invalid_json(self):
        self.assertEqual(
            self.client.post(
                "/api/routes", data="{", content_type="application/json"
            ).status_code,
            400,
        )

    def test_json_list(self):
        self.assertEqual(
            self.client.post(
                "/api/routes", data="[]", content_type="application/json"
            ).status_code,
            400,
        )

    def test_bad_inputs_never_call_provider(self):
        good = {
            "origin": "Chicago",
            "destination": "Detroit",
            "departure": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "load": 35000,
            "interval": 25,
        }
        with patch("routing.service.fetch") as fetch:
            for change in [
                {"origin": None},
                {"load": "nan"},
                {"load": -1},
                {"interval": 0},
                {"departure": None},
                {"departure": "2020-01-01T00:00:00Z"},
                {"departure": "2026-01-01T00:00:00"},
            ]:
                with self.subTest(change=change):
                    self.assertEqual(
                        self.client.post(
                            "/api/routes",
                            data={**good, **change},
                            content_type="application/json",
                        ).status_code,
                        400,
                    )
            fetch.assert_not_called()

    def test_provider_error(self):
        with patch("routing.views.plan", side_effect=requests.Timeout):
            r = self.client.post(
                "/api/routes", data={}, content_type="application/json"
            )
            self.assertEqual(r.status_code, 502)
            self.assertIn("provider", r.json()["error"])

    def test_no_traceback_exposure(self):
        with patch("routing.views.plan", side_effect=RuntimeError("secret diagnostic")):
            with self.assertLogs("routing.views", level="ERROR"):
                r = self.client.post(
                    "/api/routes", data={}, content_type="application/json"
                )
            self.assertEqual(r.status_code, 500)
            self.assertNotIn("secret", r.content.decode())

    def test_missing_weather_is_not_low(self):
        h = {
            "time": ["2026-01-01T00:00"],
            "wind_speed_10m": [None],
            "rain": [0],
            "showers": [0],
            "snowfall": [0],
        }
        with self.assertRaises(ValueError):
            sample(h, datetime(2026, 1, 1, tzinfo=timezone.utc), 0)
