import unittest
from datetime import datetime, timezone
from .service import checkpoints, sample


class ServiceTests(unittest.TestCase):
    def test_checkpoint_eta_uses_edge_duration(self):
        raw = {
            "geometry": {"coordinates": [[0, 0], [1, 0], [2, 0]]},
            "legs": [
                {
                    "annotation": {
                        "distance": [16093.44, 16093.44],
                        "duration": [100, 900],
                    }
                }
            ],
        }
        p = checkpoints(raw, 10, datetime(2026, 1, 1, tzinfo=timezone.utc))
        self.assertEqual(len(p), 3)
        self.assertEqual(p[1]["lon"], 1)
        self.assertEqual(p[1]["eta"], "2026-01-01T00:01:40+00:00")
        self.assertAlmostEqual(p[-1]["mile"], 20)

    def test_units_and_enclosing_hour(self):
        h = {
            "time": ["2026-01-01T00:00", "2026-01-01T01:00"],
            "wind_speed_10m": [0, 35],
            "rain": [0, 2.54],
            "showers": [0, 2.54],
            "snowfall": [0, 2.54],
        }
        p = sample(h, datetime(2026, 1, 1, 0, 30, tzinfo=timezone.utc), 40001)
        self.assertEqual(p["rain"], 0.2)
        self.assertEqual(p["snow"], 1)
        self.assertEqual(p["risk"], 3)
        with self.assertRaises(ValueError):
            sample(h, datetime(2026, 1, 2, tzinfo=timezone.utc), 0)

    def test_multileg_eta(self):
        raw = {
            "geometry": {"coordinates": [[0, 0], [1, 0], [2, 0]]},
            "legs": [
                {"annotation": {"distance": [16093.44], "duration": [100]}},
                {"annotation": {"distance": [16093.44], "duration": [900]}},
            ],
        }
        p = checkpoints(raw, 10, datetime(2026, 1, 1, tzinfo=timezone.utc))
        self.assertEqual(p[-1]["eta"], "2026-01-01T00:16:40+00:00")
        self.assertEqual(p[-1]["lon"], 2)
