import React, { useState, useEffect, useRef } from "react";
import { createRoot } from "react-dom/client";
import {
  MapContainer,
  TileLayer,
  Polyline,
  CircleMarker,
  Popup,
  useMap,
} from "react-leaflet";
import "leaflet/dist/leaflet.css";
import "./style.css";
import WeatherHeatmap from "./WeatherHeatmap";
const colors = ["#28a67a", "#e6b348", "#ed873b", "#da5265", "#792d56"];
const labels = ["Low", "Moderate", "High", "Severe", "No Travel"];
const localDate = () => {
  const d = new Date();
  return new Date(d - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
};
function Fit({ data }) {
  const map = useMap();
  useEffect(() => {
    if (data)
      map.fitBounds(
        data.routes.flatMap((r) =>
          r.geometry.coordinates.map(([x, y]) => [y, x]),
        ),
        { padding: [35, 35] },
      );
  }, [data, map]);
  return null;
}
function App() {
  const guide = useRef(null);
  const [form, setForm] = useState({
    origin: "Chicago",
    destination: "Detroit",
    departure: localDate(),
    load: 35000,
    interval: 25,
  });
  const [data, setData] = useState(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [selected, setSelected] = useState(0),
    [hour, setHour] = useState(0),
    [heat, setHeat] = useState(true),
    [playing, setPlaying] = useState(false);
  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => setHour((h) => (h + 1) % 49), 650);
    return () => clearInterval(id);
  }, [playing]);
  const update = (e) => setForm({ ...form, [e.target.name]: e.target.value });
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setPlaying(false);
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 210000);
    try {
      const response = await fetch("/api/routes", {
        method: "POST",
        signal: controller.signal,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...form,
          departure: new Date(form.departure).toISOString(),
        }),
      });
      if (!response.headers.get("content-type")?.includes("application/json"))
        throw Error(
          "The route service is temporarily unavailable. Please retry.",
        );
      const result = await response.json();
      if (!response.ok) throw Error(result.error);
      setData(result);
      setSelected(result.recommended ?? 0);
      setHour(0);
    } catch (e) {
      setError(
        e.name === "AbortError"
          ? "The providers took too long. Please try again."
          : e.message,
      );
    } finally {
      clearTimeout(timeout);
      setBusy(false);
    }
  }
  const route = data?.routes[selected];
  return (
    <div className="app">
      <header className="clean-header">
        <a className="brand" href="/" aria-label="Spotter home">
          spotter
        </a>
        <span className="header-description">Weather-aware route planning</span>
        <button
          className="guide-button"
          onClick={() => guide.current.showModal()}
        >
          Risk guide
        </button>
      </header>
      <dialog ref={guide} className="risk-dialog" aria-labelledby="guide-title">
        <div className="dialog-heading">
          <h2 id="guide-title">Understand your route risk</h2>
          <button
            aria-label="Close risk guide"
            onClick={() => guide.current.close()}
          >
            Close
          </button>
        </div>
        <p>
          The highest weather risk at each checkpoint applies. Load rules can
          raise that risk.
        </p>
        <div className="tablewrap">
          <table>
            <thead>
              <tr>
                <th>Risk</th>
                <th>Wind (mph)</th>
                <th>Rain (in/hr)</th>
                <th>Snow (in/hr)</th>
              </tr>
            </thead>
            <tbody>
              {[
                ["Low", "<25", "<0.10", "<0.5"],
                ["Moderate", "25–<35", "0.10–<0.25", "0.5–<1"],
                ["High", "35–<45", "0.25–<0.50", "1–<2"],
                ["Severe", "45–<55", "0.50–1.00", "2–3"],
                ["No Travel", "≥55", ">1.00", ">3"],
              ].map((row) => (
                <tr key={row[0]}>
                  {row.map((v) => (
                    <td key={v}>{v}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <ul>
          <li>45 mph or higher + more than 30,000 lb: No Travel.</li>
          <li>35 mph or higher + more than 40,000 lb: at least Severe.</li>
          <li>55 mph or higher: No Travel for every load.</li>
        </ul>
        <p>
          Recommendation order: fewest Severe miles → fewest High miles → lowest
          distance-weighted risk → shortest time. No Travel routes are excluded.
        </p>
        <p className="dialog-note">
          Routing: OSRM · Weather:{" "}
          <a
            href="https://www.weatherapi.com/"
            target="_blank"
            rel="noreferrer"
          >
            WeatherAPI.com
          </a>{" "}
          / Open-Meteo · Map: OpenStreetMap. Routes use a passenger-car profile
          and do not validate truck restrictions. Forecast colors are
          interpolated estimates, not radar. WeatherAPI total precipitation is
          compared conservatively to rain thresholds.
        </p>
      </dialog>
      <main>
        <aside>
          <div className="eyebrow">PLAN WITH CONFIDENCE</div>
          <h1>
            A clearer road <br />
            ahead.
          </h1>
          <p className="intro">
            Compare the weather along your journey.
            <br />
            Find the route that fits your load.
          </p>
          <form onSubmit={submit}>
            <div className="locations">
              <label>
                Origin city
                <input
                  name="origin"
                  value={form.origin}
                  onChange={update}
                  required
                  placeholder="City or town"
                />
              </label>
              <span className="connector">↕</span>
              <label>
                Destination city
                <input
                  name="destination"
                  value={form.destination}
                  onChange={update}
                  required
                />
              </label>
            </div>
            <label>
              Departure · your local time
              <input
                type="datetime-local"
                name="departure"
                value={form.departure}
                onChange={update}
                required
              />
            </label>
            <div className="two">
              <label>
                Load weight <span>lb</span>
                <input
                  type="number"
                  name="load"
                  min="0"
                  max="200000"
                  value={form.load}
                  onChange={update}
                  required
                />
              </label>
              <label>
                Check weather every
                <select name="interval" value={form.interval} onChange={update}>
                  <option value="10">10 miles</option>
                  <option value="25">25 miles</option>
                  <option value="50">50 miles</option>
                </select>
              </label>
            </div>
            <button className="primary" disabled={busy}>
              {busy ? "Checking roads & weather…" : "Find the best route"}{" "}
              <span>→</span>
            </button>
          </form>
          {busy && (
            <p className="loading-note" role="status">
              Comparing roads and sampling forecasts across the corridor. This
              may take a moment.
            </p>
          )}
          {error && (
            <div className="error" role="alert">
              {error}
            </div>
          )}
          <div aria-live="polite">
            {data ? (
              <>
                <div className="sectiontitle">
                  YOUR ROUTE OPTIONS <span>{data.routes.length} available</span>
                </div>
                {data.recommended === null && (
                  <div className="error">
                    No recommended route: all options have No Travel conditions.
                  </div>
                )}
                {data.routes.map((r, i) => (
                  <button
                    key={i}
                    className={"routecard " + (selected === i ? "active" : "")}
                    onClick={() => setSelected(i)}
                  >
                    <div className="cardtop">
                      <b>Route {String(i + 1).padStart(2, "0")}</b>
                      <span className={r.summary.blocked ? "blocked" : "badge"}>
                        {r.summary.blocked
                          ? "No Travel"
                          : data.recommended === i
                            ? "Recommended"
                            : "Alternative"}
                      </span>
                    </div>
                    <p className="routesource">
                      {r.source}
                      {r.via ? ` · ${r.via}` : ""}
                    </p>
                    <div className="metrics">
                      <strong>
                        {Math.floor(Math.round(r.summary.seconds / 60) / 60)}
                        <small>h </small>
                        {Math.round(r.summary.seconds / 60) % 60}
                        <small>m</small>
                      </strong>
                      <span>{r.summary.miles} miles</span>
                    </div>
                    <div className="riskbar">
                      {r.summary.exposure.map((m, j) => (
                        <span
                          key={j}
                          style={{
                            width: `${(m / r.summary.miles) * 100}%`,
                            background: colors[j],
                          }}
                        />
                      ))}
                    </div>
                    <div className="cardbottom">
                      <span>{r.summary.exposure[3].toFixed(1)} severe mi</span>
                      <span>{r.summary.exposure[2].toFixed(1)} high mi</span>
                      <span>{r.summary.average.toFixed(2)} avg risk</span>
                    </div>
                  </button>
                ))}
              </>
            ) : (
              <div className="empty">
                <span>◎</span>
                <b>Your next journey starts here</b>
                <p>
                  Enter two cities to compare routes and see forecast conditions
                  at each stop.
                </p>
              </div>
            )}
          </div>
          <p className="footnote">
            Assessment prototype · Weather guidance only.
            <br />
            Truck height, weight restrictions and driver breaks are not
            included.
          </p>
        </aside>
        <section className="workspace">
          <div className="mapheading">
            <div>
              <div className="eyebrow">YOUR ROUTE OVERVIEW</div>
              <h2>
                {data
                  ? `${data.origin.name} → ${data.destination.name}`
                  : "Every mile, in view."}
              </h2>
            </div>
            <span className="livebadge">
              {data
                ? `${data.weather_provider || "Live"} forecast loaded`
                : "Ready to plan"}
            </span>
          </div>
          <div className="map">
            <MapContainer center={[41.9, -85.4]} zoom={6} zoomControl={true}>
              <TileLayer
                attribution="&copy; OpenStreetMap contributors"
                url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              <Fit data={data} />
              <WeatherHeatmap data={data} hour={hour} visible={heat} />
              {data?.routes.map((r, i) => (
                <Polyline
                  key={i}
                  positions={r.geometry.coordinates.map(([x, y]) => [y, x])}
                  pathOptions={{
                    color: i === selected ? "#215b52" : "#889eaa",
                    weight: i === selected ? 6 : 3,
                    opacity: i === selected ? 0.95 : 0.5,
                  }}
                  eventHandlers={{ click: () => setSelected(i) }}
                />
              ))}
              {route?.points.map((p, i) => (
                <React.Fragment key={i}>
                  <CircleMarker
                    center={[p.lat, p.lon]}
                    radius={5}
                    pathOptions={{
                      color: "#fff",
                      weight: 2,
                      fillColor: colors[p.risk],
                      fillOpacity: 1,
                    }}
                  >
                    <Popup>
                      <b>
                        Checkpoint {i + 1} · {p.mile.toFixed(1)} mi
                      </b>
                      <br />
                      {labels[p.risk]} at arrival
                      <br />
                      ETA: {new Date(p.eta).toLocaleString()}
                      <br />
                      Wind: {p.wind} mph
                      <br />
                      {data.weather_provider === "WeatherAPI.com"
                        ? "Precip"
                        : "Rain"}
                      : {p.rain} in/hr · Snow: {p.snow} in/hr
                    </Popup>
                  </CircleMarker>
                </React.Fragment>
              ))}
            </MapContainer>
            <div className="maplegend">
              {labels.map((name, i) => (
                <span key={name}>
                  <i style={{ background: colors[i] }} />
                  {name}
                </span>
              ))}
            </div>
          </div>
          <div className="forecast">
            <div>
              <b>
                Weather corridor{" "}
                <span className="forecast-tag">48H FORECAST</span>
              </b>
              <p>
                Shading: forecast at departure + {hour}h · Dots: arrival-time
                risk
              </p>
            </div>
            <label className="toggle">
              <input
                type="checkbox"
                checked={heat}
                onChange={(e) => setHeat(e.target.checked)}
              />{" "}
              Show overlay
            </label>
            <div className="timeline">
              <button
                type="button"
                className="play"
                disabled={!data}
                aria-label={playing ? "Pause forecast" : "Play forecast"}
                onClick={() => setPlaying(!playing)}
              >
                {playing ? "Pause" : "Play"}
              </button>
              <span>Departure</span>
              <input
                aria-label="Forecast hour after departure"
                type="range"
                min="0"
                max="48"
                value={hour}
                disabled={!data}
                onChange={(e) => {
                  setHour(Number(e.target.value));
                  setPlaying(false);
                }}
              />
              <strong>+{hour}h</strong>
              <span>48h</span>
            </div>
          </div>
          {data && (
            <p className="notice">
              {data.notice} Heatmap: {data.corridor.points.length} weather grid
              samples, {data.corridor.spacing_km} km spacing, 35 km each side of
              all routes. Colors interpolate forecast risk; checkpoint dots show
              arrival risk.
            </p>
          )}
          <div className="checkpointpanel">
            <div className="sectiontitle">
              {route ? "CHECKPOINT BREAKDOWN" : "BUILT AROUND YOUR JOURNEY"}
              <span>
                {route
                  ? `${route.points.length} weather checks`
                  : "01 / 02 / 03"}
              </span>
            </div>
            {route ? (
              <div className="tablewrap">
                <table>
                  <thead>
                    <tr>
                      <th>Checkpoint</th>
                      <th>Arrival · local</th>
                      <th>Wind</th>
                      <th>
                        {data.weather_provider === "WeatherAPI.com"
                          ? "Precip / snow"
                          : "Rain / snow"}
                      </th>
                      <th>Risk</th>
                    </tr>
                  </thead>
                  <tbody>
                    {route.points.map((p, i) => (
                      <tr key={i}>
                        <td>
                          {String(i + 1).padStart(2, "0")}{" "}
                          <small>· {p.mile.toFixed(1)} mi</small>
                        </td>
                        <td>
                          {new Date(p.eta).toLocaleString([], {
                            month: "short",
                            day: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </td>
                        <td>{p.wind} mph</td>
                        <td>
                          {p.rain} / {p.snow} in/hr
                        </td>
                        <td>
                          <span style={{ color: colors[p.risk] }}>
                            ● {labels[p.risk]}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="features">
                <div>
                  <b>
                    01 <span>Compare your options</span>
                  </b>
                  <p>Distinct roads, one clear view.</p>
                </div>
                <div>
                  <b>
                    02 <span>Look ahead</span>
                  </b>
                  <p>Weather matched to your arrival.</p>
                </div>
                <div>
                  <b>
                    03 <span>Account for your load</span>
                  </b>
                  <p>Risk rules that reflect your cargo.</p>
                </div>
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}
createRoot(document.getElementById("root")).render(<App />);
