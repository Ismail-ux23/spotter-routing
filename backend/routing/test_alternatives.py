import unittest
from unittest.mock import Mock
from .alternatives import find_routes
from .corridor import corridor_grid


def route(coords):
    return {"geometry": {"coordinates": coords}, "duration": 1000, "distance": 100000}


class AlternativeTests(unittest.TestCase):
    def test_waypoints_fill_missing_routes(self):
        a = route([[0, 0], [1, 0], [2, 0]])
        b = route([[0, 0], [1, 1], [2, 0]])
        c = route([[0, 0], [1, -1], [2, 0]])
        fetch = Mock(
            side_effect=[
                {"code": "Ok", "routes": [a, a]},
                {"routes": [b]},
                {"routes": [c]},
            ]
        )
        result = find_routes({"lon": 0, "lat": 0}, {"lon": 2, "lat": 0}, fetch)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[-1]["source"], "Via-road alternative")

    def test_does_not_invent_third_route(self):
        a = route([[0, 0], [1, 0], [2, 0]])
        fetch = Mock(return_value={"code": "Ok", "routes": [a]})
        self.assertEqual(
            len(find_routes({"lon": 0, "lat": 0}, {"lon": 2, "lat": 0}, fetch)), 1
        )

    def test_grid_covers_between_checkpoints_and_off_road(self):
        grid = corridor_grid([route([[0, 0], [2, 0]])])
        self.assertLessEqual(len(grid["points"]), 180)
        self.assertTrue(any(abs(p["lat"]) > 0.1 for p in grid["points"]))
        self.assertTrue(any(0.8 < p["lon"] < 1.2 for p in grid["points"]))

    def test_grid_adapts_to_budget(self):
        grid = corridor_grid([route([[0, 0], [12, 0]])], limit=100)
        self.assertLessEqual(len(grid["points"]), 100)
        self.assertGreater(grid["spacing_km"], 25)
