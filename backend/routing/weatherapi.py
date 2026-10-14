"""WeatherAPI adapter using only the three-day Free-plan forecast endpoint."""

import hashlib
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from django.core.cache import cache

BASE_URL = "https://api.weatherapi.com/v1/"


def api_key():
    key = os.environ.get("WEATHERAPI_KEY", "").strip()
    if key:
        return key
    path = Path.home() / ".weatherapi-key"
    return path.read_text().strip() if path.is_file() else ""


def geocode(name, fetch):
    data = fetch(BASE_URL + "search.json", {"key": api_key(), "q": name})
    if not isinstance(data, list) or not data:
        raise ValueError(f"City not found: {name}")
    p = data[0]
    return {
        "name": f"{p['name']}, {p.get('region') or p.get('country', '')}",
        "lat": p["lat"],
        "lon": p["lon"],
    }


def normalize(data):
    rows = [
        h
        for day in data.get("forecast", {}).get("forecastday", [])
        for h in day.get("hour", [])
    ]
    if not rows:
        raise ValueError("WeatherAPI returned no hourly forecasts.")
    rows.sort(key=lambda h: h["time_epoch"])
    hourly = {k: [] for k in ("time", "wind_speed_10m", "rain", "showers", "snowfall")}
    hourly["interval_start"] = True
    for row in rows:
        hourly["time"].append(
            datetime.fromtimestamp(row["time_epoch"], timezone.utc)
            .replace(tzinfo=None)
            .isoformat()
        )
        # Total precipitation is used conservatively for the rain threshold.
        # Missing observations remain missing; they must never become zero risk.
        hourly["wind_speed_10m"].append(row.get("wind_mph"))
        hourly["rain"].append(row.get("precip_mm"))
        hourly["showers"].append(0)
        hourly["snowfall"].append(row.get("snow_cm"))
    return {"hourly": hourly}


def weather(points, fetch):
    secret = api_key()
    account = hashlib.sha256(secret.encode()).hexdigest()[:16]
    day = datetime.now(timezone.utc).date().isoformat()
    coords = [(round(p["lat"], 4), round(p["lon"], 4)) for p in points]

    def load(coord):
        key = f"weatherapi-v1:{account}:{day}:{coord[0]}:{coord[1]}"
        cached = cache.get(key)
        if cached is not None:
            return cached
        data = fetch(
            BASE_URL + "forecast.json",
            {
                "key": secret,
                "q": f"{coord[0]},{coord[1]}",
                "days": 3,
                "aqi": "no",
                "alerts": "no",
            },
        )
        result = normalize(data)
        cache.set(key, result, 3600)
        return result

    unique = list(dict.fromkeys(coords))
    # Free accounts do not support bulk calls. Bound concurrency and cache nodes.
    with ThreadPoolExecutor(max_workers=4) as pool:
        found = dict(zip(unique, pool.map(load, unique)))
    return [found[coord] for coord in coords]
