"""Geographic weather grid clipped to a buffer around all route geometries."""

import math


def corridor_grid(routes, spacing_km=25, width_km=35, limit=180):
    coords = [p for route in routes for p in route["geometry"]["coordinates"]]
    lat0 = sum(p[1] for p in coords) / len(coords)
    lon_scale = 111.32 * max(0.2, math.cos(math.radians(lat0)))
    lines = [
        [(p[0] * lon_scale, p[1] * 111.32) for p in r["geometry"]["coordinates"]]
        for r in routes
    ]
    # Reduce segment count without leaving gaps: use connected simplified vertices.
    simplified = []
    for line in lines:
        reduced = [line[0]]
        for p in line[1:-1]:
            if math.dist(p, reduced[-1]) >= 5:
                reduced.append(p)
        reduced.append(line[-1])
        simplified.extend(zip(reduced, reduced[1:]))

    def distance2(x, y, a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]
        t = max(
            0,
            min(
                1, ((x - a[0]) * dx + (y - a[1]) * dy) / max(dx * dx + dy * dy, 0.00001)
            ),
        )
        return (x - a[0] - t * dx) ** 2 + (y - a[1] - t * dy) ** 2

    xs = [p[0] * lon_scale for p in coords]
    ys = [p[1] * 111.32 for p in coords]
    spacing = spacing_km
    while True:
        nodes = []
        for ix in range(
            math.floor((min(xs) - width_km) / spacing),
            math.ceil((max(xs) + width_km) / spacing) + 1,
        ):
            for iy in range(
                math.floor((min(ys) - width_km) / spacing),
                math.ceil((max(ys) + width_km) / spacing) + 1,
            ):
                x, y = ix * spacing, iy * spacing
                if any(distance2(x, y, a, b) <= width_km**2 for a, b in simplified):
                    nodes.append({"lon": x / lon_scale, "lat": y / 111.32})
        if len(nodes) <= limit:
            break
        spacing *= 1.3
    return {"points": nodes, "spacing_km": round(spacing, 1), "width_km": width_km}
