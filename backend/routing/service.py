import math
import hashlib
import time
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse
from datetime import datetime, timedelta, timezone
import requests
from django.core.cache import cache
from .risk import classify, summarize, recommend
from .alternatives import find_routes
from .corridor import corridor_grid

MILE = 1609.344


class ProviderRateLimit(requests.RequestException):
    def __init__(self, provider, retry_after):
        self.retry_after = max(1, int(retry_after))
        minutes = math.ceil(self.retry_after / 60)
        super().__init__(
            f"{provider} has reached its request limit. Try again in about {minutes} minute(s). "
            "No new provider requests will be sent during this cooldown."
        )


def retry_delay(response):
    value = response.headers.get("Retry-After", "")
    try:
        return max(1, math.ceil(float(value)))
    except (ValueError, OverflowError):
        try:
            return max(
                1, math.ceil(parsedate_to_datetime(value).timestamp() - time.time())
            )
        except (ValueError, TypeError, OverflowError):
            pass
    try:
        reason = str(response.json().get("reason", "")).lower()
    except (ValueError, AttributeError):
        reason = ""
    if "day" in reason or "daily" in reason:
        return 86400
    if "hour" in reason:
        return 3600
    return 60


def fetch(url, params):
    key = hashlib.sha256((url + str(sorted(params.items()))).encode()).hexdigest()
    cached = cache.get(key)
    if cached is not None:
        return cached
    host = urlparse(url).hostname
    provider = "Open-Meteo weather" if host == "api.open-meteo.com" else host
    cooldown_key = "provider-cooldown:" + host
    until = cache.get(cooldown_key, 0)
    if until > time.time():
        raise ProviderRateLimit(provider, math.ceil(until - time.time()))
    response = requests.get(url, params=params, timeout=35)
    if response.status_code == 429:
        delay = retry_delay(response)
        cache.set(cooldown_key, time.time() + delay, delay)
        raise ProviderRateLimit(provider, delay)
    response.raise_for_status()
    data = response.json()
    cache.set(key, data, 600)
    return data


def geocode(name):
    data = fetch(
        "https://geocoding-api.open-meteo.com/v1/search",
        {"name": name, "count": 1, "language": "en"},
    )
    if not data.get("results"):
        raise ValueError(f"City not found: {name}")
    p = data["results"][0]
    return {
        "name": f"{p['name']}, {p.get('admin1', p.get('country', ''))}",
        "lat": p["latitude"],
        "lon": p["longitude"],
    }


def haversine(a, b):
    lat1, lat2 = map(math.radians, (a[1], b[1]))
    dlat, dlon = lat2 - lat1, math.radians(b[0] - a[0])
    return (
        6371000
        * 2
        * math.asin(
            min(
                1,
                math.sqrt(
                    math.sin(dlat / 2) ** 2
                    + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
                ),
            )
        )
    )


def checkpoints(route, interval, departure):
    coords = route["geometry"]["coordinates"]
    distances = [d for leg in route["legs"] for d in leg["annotation"]["distance"]]
    durations = [d for leg in route["legs"] for d in leg["annotation"]["duration"]]
    if (
        len(coords) != len(distances) + 1
        or len(durations) != len(distances)
        or not distances
    ):
        raise ValueError("Routing provider returned inconsistent geometry.")
    if any(not math.isfinite(v) or v < 0 for v in distances + durations):
        raise ValueError("Routing provider returned invalid distances or durations.")
    total = sum(distances)
    if total <= 0:
        raise ValueError("Origin and destination resolve to the same road location.")
    targets = [i * interval * MILE for i in range(int(total / (interval * MILE)) + 1)]
    if total - targets[-1] > 0.01:
        targets.append(total)
    points = []
    edge = 0
    covered = 0
    elapsed = 0
    for target in targets:
        while edge < len(distances) - 1 and covered + distances[edge] < target:
            covered += distances[edge]
            elapsed += durations[edge]
            edge += 1
        f = min(1, max(0, (target - covered) / max(distances[edge], 0.001)))
        a, b = coords[edge], coords[edge + 1]
        points.append(
            {
                "lon": a[0] + (b[0] - a[0]) * f,
                "lat": a[1] + (b[1] - a[1]) * f,
                "mile": target / MILE,
                "eta": (
                    departure + timedelta(seconds=elapsed + durations[edge] * f)
                ).isoformat(),
            }
        )
    return points


def weather(points):
    # Cache forecasts by exact requested coordinate, independent of route/load.
    # A shared checkpoint is fetched once; valid data survives web-worker reloads.
    coordinates = [(round(p["lat"], 4), round(p["lon"], 4)) for p in points]
    day = datetime.now(timezone.utc).date().isoformat()

    def key(coord):
        return f"weather-v1:{day}:{coord[0]}:{coord[1]}"

    found = {}
    for coord in dict.fromkeys(coordinates):
        item = cache.get(key(coord))
        if item is not None:
            found[coord] = item
    missing = [coord for coord in dict.fromkeys(coordinates) if coord not in found]
    for start in range(0, len(missing), 40):
        batch = missing[start : start + 40]
        data = fetch(
            "https://api.open-meteo.com/v1/forecast",
            {
                "latitude": ",".join(str(lat) for lat, lon in batch),
                "longitude": ",".join(str(lon) for lat, lon in batch),
                "hourly": "wind_speed_10m,rain,showers,snowfall",
                "wind_speed_unit": "mph",
                "precipitation_unit": "mm",
                "timezone": "GMT",
                "forecast_days": 7,
            },
        )
        items = data if isinstance(data, list) else [data]
        if len(items) != len(batch):
            raise ValueError("Weather provider returned an incomplete forecast batch.")
        for coord, item in zip(batch, items):
            if not isinstance(item, dict) or not item.get("hourly"):
                raise ValueError("Weather provider returned missing forecast data.")
            found[coord] = item
            cache.set(key(coord), item, 3600)
    return [found[coord] for coord in coordinates]


def sample(hourly, when, load):
    target = when.astimezone(timezone.utc).replace(tzinfo=None)
    times = [datetime.fromisoformat(t) for t in hourly["time"]]
    # Precipitation is the preceding hour's accumulation; use the enclosing hour.
    idx = next((i for i, t in enumerate(times) if t >= target), None)
    if idx is None or target < times[0]:
        raise ValueError(
            "Trip extends outside available forecast. Choose an earlier departure."
        )
    values = [hourly[k][idx] for k in ("wind_speed_10m", "rain", "showers", "snowfall")]
    if any(
        v is None or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0
        for v in values
    ):
        raise ValueError("Weather provider returned missing forecast data.")
    wind, rain, showers, snow = values
    rain = (rain + showers) / 25.4
    snow = snow / 2.54
    return dict(
        wind=round(wind, 1),
        rain=round(rain, 3),
        snow=round(snow, 3),
        risk=classify(wind, rain, snow, load),
    )


def plan(payload):
    origin = payload.get("origin", "")
    destination = payload.get("destination", "")
    if not isinstance(origin, str) or not isinstance(destination, str):
        raise ValueError("Origin and destination must be city names.")
    origin = origin.strip()
    destination = destination.strip()
    if len(origin) > 150 or len(destination) > 150:
        raise ValueError("City names are too long.")
    if not origin or not destination:
        raise ValueError("Enter origin and destination cities.")
    load = float(payload.get("load", 0))
    interval = int(payload.get("interval", 25))
    if not math.isfinite(load) or load < 0 or load > 200000:
        raise ValueError("Load must be between 0 and 200,000 lb.")
    if interval not in (10, 25, 50):
        raise ValueError("Choose 10, 25 or 50 mile sampling.")
    if not isinstance(payload.get("departure"), str):
        raise ValueError("Enter a valid departure date and time.")
    departure = datetime.fromisoformat(payload["departure"].replace("Z", "+00:00"))
    if departure.tzinfo is None:
        raise ValueError("Departure must include a timezone.")
    now = datetime.now(timezone.utc)
    if departure < now - timedelta(minutes=5) or departure > now + timedelta(days=4):
        raise ValueError("Departure must be within the next four days.")
    a, b = geocode(origin), geocode(destination)
    raw_routes = find_routes(a, b, fetch)
    routes = []
    for raw in raw_routes:
        points = checkpoints(raw, interval, departure)
        if len(points) > 180:
            raise ValueError(
                "Trip too long for this demo. Increase checkpoint spacing or choose closer cities."
            )
        forecasts = weather(points)
        for p, forecast in zip(points, forecasts):
            p.update(sample(forecast["hourly"], datetime.fromisoformat(p["eta"]), load))
            p["forecast"] = [
                sample(forecast["hourly"], departure + timedelta(hours=h), load)["risk"]
                for h in range(49)
            ]
        routes.append(
            {
                "geometry": raw["geometry"],
                "source": raw["source"],
                "via": raw.get("via"),
                "points": points,
                "summary": summarize(points, points[-1]["mile"], raw["duration"]),
            }
        )
    corridor = corridor_grid(raw_routes)
    for p, forecast in zip(corridor["points"], weather(corridor["points"])):
        p["forecast"] = [
            sample(forecast["hourly"], departure + timedelta(hours=h), load)["risk"]
            for h in range(49)
        ]
    count = len(routes)
    return {
        "origin": a,
        "destination": b,
        "routes": routes,
        "recommended": recommend(routes),
        "corridor": corridor,
        "complete": count == 3,
        "notice": (
            f"{count} distinct road routes found. "
            if count == 3
            else f"Only {count} distinct routes found after checking detours. "
        )
        + "Passenger-car routing profile; truck restrictions are not checked.",
        "departure": departure.isoformat(),
    }
