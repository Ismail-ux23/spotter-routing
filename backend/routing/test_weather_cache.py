import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
import django

django.setup()
from unittest.mock import Mock, patch
from django.test import SimpleTestCase, override_settings
from django.core.cache import cache
from .service import weather, fetch, ProviderRateLimit, retry_delay


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
)
class WeatherCacheTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_same_location_only_fetched_once_and_order_preserved(self):
        a = {"lat": 1, "lon": 2}
        b = {"lat": 3, "lon": 4}
        f1 = {"hourly": {"time": ["one"]}}
        f2 = {"hourly": {"time": ["two"]}}
        with patch("routing.service.fetch", return_value=[f1, f2]) as call:
            self.assertEqual(weather([a, b, a]), [f1, f2, f1])
            self.assertEqual(weather([b, a]), [f2, f1])
            call.assert_called_once()
            self.assertEqual(call.call_args.args[1]["latitude"], "1,3")

    def test_expired_forecast_is_refetched(self):
        with patch(
            "routing.service.fetch", return_value={"hourly": {"time": ["x"]}}
        ) as call:
            weather([{"lat": 1, "lon": 2}])
            cache.clear()
            weather([{"lat": 1, "lon": 2}])
            self.assertEqual(call.call_count, 2)

    def test_429_stops_followup_requests(self):
        response = Mock(status_code=429, headers={"Retry-After": "120"})
        with patch("routing.service.requests.get", return_value=response) as get:
            for lat in (1, 2):
                with self.assertRaises(ProviderRateLimit) as error:
                    fetch("https://api.open-meteo.com/v1/forecast", {"latitude": lat})
                self.assertGreaterEqual(error.exception.retry_after, 119)
            get.assert_called_once()

    def test_daily_limit_uses_long_cooldown(self):
        r = Mock(headers={})
        r.json.return_value = {"reason": "Daily API request limit exceeded"}
        self.assertEqual(retry_delay(r), 86400)

    def test_api_returns_actionable_429(self):
        with override_settings(ALLOWED_HOSTS=["testserver"]):
            with patch(
                "routing.views.plan",
                side_effect=ProviderRateLimit("Open-Meteo weather", 120),
            ):
                r = self.client.post(
                    "/api/routes", data={}, content_type="application/json"
                )
                self.assertEqual(r.status_code, 429)
                self.assertEqual(r.headers["Retry-After"], "120")

    def test_missing_data_is_not_cached(self):
        with patch("routing.service.fetch", return_value={}):
            with self.assertRaises(ValueError):
                weather([{"lat": 1, "lon": 2}])
