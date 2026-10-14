"""Bounded road-network alternatives; never duplicate geometry to fill cards."""

import math
import requests


def cells(route):
    return {(round(x, 2), round(y, 2)) for x, y in route["geometry"]["coordinates"]}


def distinct(route, existing):
    a = cells(route)
    return all(len(a & cells(r)) / max(1, len(a | cells(r))) < 0.94 for r in existing)


def find_routes(a, b, fetch):
    def query(coords, alternatives):
        url = "https://router.project-osrm.org/route/v1/driving/" + ";".join(
            f"{x},{y}" for x, y in coords
        )
        return fetch(
            url,
            {
                "alternatives": str(alternatives),
                "overview": "full",
                "geometries": "geojson",
                "annotations": "distance,duration",
                "steps": "false",
                "continue_straight": "true",
            },
        )

    start, end = (a["lon"], a["lat"]), (b["lon"], b["lat"])
    if abs(start[0] - end[0]) + abs(start[1] - end[1]) < 0.001:
        raise ValueError("Choose different origin and destination cities.")
    data = query([start, end], 3)
    if data.get("code") != "Ok" or not data.get("routes"):
        raise ValueError("No drivable route found between these cities.")
    found = []
    for route in data["routes"]:
        if distinct(route, found):
            route["source"] = "Direct alternative"
            found.append(route)
    base = data["routes"][0]
    # Offset a midpoint perpendicular to the trip, then let OSRM snap to roads.
    cos = max(0.2, math.cos(math.radians((start[1] + end[1]) / 2)))
    dx = (end[0] - start[0]) * cos
    dy = end[1] - start[1]
    length = math.hypot(dx, dy)
    for fraction, scale, side in [
        (0.5, 0.12, 1),
        (0.5, 0.12, -1),
        (0.35, 0.22, 1),
        (0.65, 0.22, -1),
        (0.5, 0.35, 1),
        (0.5, 0.35, -1),
    ]:
        if len(found) >= 3:
            break
        offset = min(0.9, max(0.12, length * scale))
        via = (
            start[0]
            + (end[0] - start[0]) * fraction
            - dy / length * offset * side / cos,
            start[1] + (end[1] - start[1]) * fraction + dx / length * offset * side,
        )
        try:
            candidate = query([start, via, end], "false")
        except requests.RequestException:
            continue
        for route in candidate.get("routes", []):
            if (
                route["duration"] > base["duration"] * 2.2
                or route["distance"] > base["distance"] * 2.2
            ):
                continue
            if distinct(route, found):
                route["source"] = "Via-road alternative"
                route["via"] = (
                    candidate.get("waypoints", [{}, {}])[1].get("name")
                    or "Intermediate road"
                )
                found.append(route)
    return found[:3]
