"""Pure, distance-weighted assessment rules. Units: mph, inches/hour, pounds."""

LABELS = ["Low", "Moderate", "High", "Severe", "No Travel"]


def classify(wind, rain, snow, load):
    if min(wind, rain, snow, load) < 0:
        raise ValueError("Weather and load must be non-negative")
    w = sum(wind >= t for t in (25, 35, 45, 55))
    r = 4 if rain > 1 else sum(rain >= t for t in (0.1, 0.25, 0.5))
    s = 4 if snow > 3 else sum(snow >= t for t in (0.5, 1, 2))
    if wind >= 55 or (wind >= 45 and load > 30000):
        w = 4
    elif wind >= 35 and load > 40000:
        w = max(w, 3)
    return max(w, r, s)


def summarize(points, miles, seconds):
    exposure = [0.0] * 5
    for a, b in zip(points, points[1:]):
        exposure[max(a["risk"], b["risk"])] += b["mile"] - a["mile"]
    return dict(
        miles=round(miles, 1),
        seconds=seconds,
        exposure=exposure,
        average=sum(i * m for i, m in enumerate(exposure)) / max(miles, 0.001),
        blocked=any(p["risk"] == 4 for p in points),
    )


def recommend(routes):
    eligible = [i for i, r in enumerate(routes) if not r["summary"]["blocked"]]
    return (
        min(
            eligible,
            key=lambda i: (
                routes[i]["summary"]["exposure"][3],
                routes[i]["summary"]["exposure"][2],
                routes[i]["summary"]["average"],
                routes[i]["summary"]["seconds"],
            ),
        )
        if eligible
        else None
    )
