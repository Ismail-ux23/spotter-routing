import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
import django

django.setup()
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings
from . import weatherapi
from .service import sample, fetch, ProviderError, plan


def forecast():
    start = datetime(2026, 10, 15, tzinfo=timezone.utc)
    return {
        "forecast": {
            "forecastday": [
                {
                    "hour": [
                        {
                            "time_epoch": int((start + timedelta(hours=h)).timestamp()),
                            "wind_mph": 35,
                            "precip_mm": 2.54,
                            "snow_cm": 2.54,
                        }
                        for h in range(72)
                    ]
                }
            ]
        }
    }


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
)
class WeatherAPITests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.key = patch("routing.weatherapi.api_key", return_value="test-key")
        self.key.start()
        self.addCleanup(self.key.stop)

    def test_epoch_uses_utc_and_start_of_hour(self):
        data = forecast()
        data["forecast"]["forecastday"][0]["hour"][1]["wind_mph"] = 60
        hourly = weatherapi.normalize(data)["hourly"]
        result = sample(hourly, datetime(2026, 10, 15, 0, 30, tzinfo=timezone.utc), 0)
        self.assertEqual(result["wind"], 35)
        self.assertEqual(result["rain"], 0.1)
        self.assertEqual(result["snow"], 1)
        self.assertEqual(result["risk"], 2)
        with self.assertRaises(ValueError):
            sample(hourly, datetime(2026, 10, 18, tzinfo=timezone.utc), 0)

    def test_missing_snow_does_not_become_safe_weather(self):
        data = forecast()
        del data["forecast"]["forecastday"][0]["hour"][0]["snow_cm"]
        with self.assertRaises(ValueError):
            sample(
                weatherapi.normalize(data)["hourly"],
                datetime(2026, 10, 15, tzinfo=timezone.utc),
                0,
            )

    def test_free_plan_and_duplicate_cache(self):
        call = Mock(return_value=forecast())
        p = {"lat": 41.85, "lon": -87.65}
        results = weatherapi.weather([p, p], call)
        self.assertEqual(results[0], results[1])
        weatherapi.weather([p], call)
        call.assert_called_once()
        self.assertEqual(call.call_args.args[1]["days"], 3)
        self.assertEqual(call.call_args.args[0], weatherapi.BASE_URL + "forecast.json")

    def test_provider_errors_do_not_expose_key(self):
        response = Mock(status_code=403)
        response.json.return_value = {"error": {"code": 2007}}
        with patch("routing.service.requests.get", return_value=response):
            with self.assertRaises(ProviderError) as e:
                fetch(weatherapi.BASE_URL + "forecast.json", {"key": "test-key"})
            self.assertIn("quota", str(e.exception))
            self.assertNotIn("test-key", str(e.exception))

    def test_no_open_meteo_calls_when_configured(self):
        with patch("routing.service.fetch") as call:
            call.return_value = [
                {"name": "Chicago", "region": "Illinois", "lat": 41.85, "lon": -87.65}
            ]
            from .service import geocode

            self.assertEqual(geocode("Chicago")["lat"], 41.85)
            self.assertEqual(
                call.call_args.args[0], weatherapi.BASE_URL + "search.json"
            )

    def test_late_departure_rejected_before_provider_calls(self):
        with patch("routing.service.geocode") as call:
            with self.assertRaisesRegex(ValueError, "24 hours"):
                plan(
                    {
                        "origin": "Chicago",
                        "destination": "Detroit",
                        "departure": (
                            datetime.now(timezone.utc) + timedelta(days=2)
                        ).isoformat(),
                    }
                )
            call.assert_not_called()
