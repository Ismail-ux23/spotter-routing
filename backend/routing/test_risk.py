import unittest
from .risk import classify, summarize, recommend


class RiskTests(unittest.TestCase):
    def test_wind_boundaries(self):
        for wind, expected in [
            (24.9, 0),
            (25, 1),
            (34.9, 1),
            (35, 2),
            (45, 3),
            (54.9, 3),
            (55, 4),
        ]:
            with self.subTest(wind=wind):
                self.assertEqual(classify(wind, 0, 0, 0), expected)

    def test_load_rules(self):
        self.assertEqual(classify(45, 0, 0, 30000), 3)
        self.assertEqual(classify(45, 0, 0, 30001), 4)
        self.assertEqual(classify(35, 0, 0, 40000), 2)
        self.assertEqual(classify(35, 0, 0, 40001), 3)

    def test_rain_snow(self):
        for rain, expected in [
            (0.099, 0),
            (0.1, 1),
            (0.25, 2),
            (0.5, 3),
            (1, 3),
            (1.001, 4),
        ]:
            self.assertEqual(classify(0, rain, 0, 0), expected)
        for snow, expected in [(0.49, 0), (0.5, 1), (1, 2), (2, 3), (3, 3), (3.001, 4)]:
            self.assertEqual(classify(0, 0, snow, 0), expected)

    def test_conservative_segment_weighting(self):
        s = summarize(
            [{"mile": 0, "risk": 0}, {"mile": 25, "risk": 3}, {"mile": 30, "risk": 1}],
            30,
            1800,
        )
        self.assertEqual(s["exposure"][3], 30)
        self.assertEqual(s["average"], 3)

    def test_blocked_routes_excluded(self):
        a = {
            "summary": {
                "blocked": True,
                "exposure": [0] * 5,
                "average": 0,
                "seconds": 1,
            }
        }
        b = {
            "summary": {
                "blocked": False,
                "exposure": [0, 0, 0, 1, 0],
                "average": 3,
                "seconds": 100,
            }
        }
        self.assertEqual(recommend([a, b]), 1)
        self.assertIsNone(recommend([a]))

    def test_severe_before_duration(self):
        def r(severe, seconds):
            return {
                "summary": {
                    "blocked": False,
                    "exposure": [0, 0, 0, severe, 0],
                    "average": 1,
                    "seconds": seconds,
                }
            }

        self.assertEqual(recommend([r(2, 100), r(1, 200)]), 1)
