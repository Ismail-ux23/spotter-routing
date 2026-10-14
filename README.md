# Spotter — Weather-aware truck routing

React + Django assessment implementation. Live city geocoding, road alternatives, distance-based checkpoints, ETA-specific forecasts, load-sensitive risk classification and a spatial corridor heatmap with a 0–48 hour slider and playback.

## App preview

Live Chicago–Detroit route comparison with ETA checkpoints and the corridor weather heatmap.

<img src="docs/screenshots/route-planner.jpg" alt="Spotter route planner showing three alternatives, checkpoint forecasts and weather heatmap" width="600" />

## Run locally

Backend:
```sh
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py runserver 127.0.0.1:8001
```
Frontend (separate terminal):
```sh
cd frontend
npm ci
npm run dev
```
Open http://127.0.0.1:5173. Vite proxies `/api` to Django. No API key required for these public demonstration services.

## Validation
```sh
cd backend
.venv/bin/python -m unittest discover -s . -p 'test_*.py'
.venv/bin/python manage.py check
cd ../frontend
npm run build
```

## Rules and assumptions

- Units: wind mph, rain/snow inches/hour, load pounds. Open-Meteo rain + showers are converted from mm; snowfall from cm.
- Shared rain/snow threshold boundaries use the higher risk (0.25 in/hr rain is High); exactly 1 inch rain and 3 inches snow remain Severe, as the spec explicitly uses `>` for No Travel.
- Wind uses continuous thresholds 25/35/45/55. Load overrides use strictly greater than 30,000 / 40,000 lb.
- Checkpoints interpolate full route geometry at 10/25/50 mile intervals plus both endpoints. ETA uses OSRM per-segment durations, not straight-line distance or average speed.
- Forecast precipitation represents the preceding hour; arrival samples use the enclosing hourly interval. Missing/out-of-range data fails visibly, never substitutes Low risk.
- Segment exposure conservatively uses the worse adjacent checkpoint risk. Average risk is distance weighted (0–4).
- No Travel routes are excluded. Remaining routes are ranked lexicographically by Severe miles, High miles, average risk, then travel duration.
- Departure is timezone-aware and limited to the next four days; forecasts span seven days. Both arrival and slider times must be covered.

## Implementation notes and limitations

- Requests three direct OSRM alternatives, then tries up to six perpendicular intermediate waypoints to fill missing options. Geometry-cell overlap rejects duplicates; distance/duration over 2.2× the base route is rejected. Successful Chicago–Detroit verification returns three routes. Some road networks cannot provide three valid routes; the API returns `complete: false` and an honest count in that case.
- OSRM's public driving profile is passenger-car based, not truck-restriction aware. Breaks and traffic aren't modeled.
- Full corridor heatmap samples a geographic grid within 35 km of all routes. Starts at 25 km spacing and adapts to at most 180 nodes. All 49 hourly risk values are prefetched. Canvas inverse-distance interpolation is clipped to buffered route geometry and redraws on pan/zoom/resize. It is an interpolated forecast risk field, not radar or an exact storm boundary.
- City search currently chooses the top match. Disambiguated geocoding selection remains to implement.
- Public API availability and rate limits apply. Weather requests are batched and cached for ten minutes. Production needs shared cache, request throttling, authentication as appropriate, and a job queue for long trips.

## Deployment

The Dockerfile builds React and serves it with Django using WhiteNoise and Gunicorn at one origin. The included `render.yaml` configures a Docker web service on Render, generates a secret, and uses `/api/health` for health checks.

For other Docker hosts, set `DEBUG=0`, `DJANGO_SECRET_KEY` to a random secret, and `ALLOWED_HOSTS` to the deployment hostname. Configure HTTPS at the reverse proxy. Set `TRUST_PROXY=1` only behind a trusted proxy that sets the forwarded-protocol header. The server reads its port from `PORT` (default 8000).

## References
- https://open-meteo.com/en/docs
- https://open-meteo.com/en/docs/geocoding-api
- https://project-osrm.org/docs/v5.24.0/
