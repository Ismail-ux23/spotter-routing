import { useEffect } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";
const palette = [
  [40, 166, 122],
  [230, 179, 72],
  [237, 135, 59],
  [218, 82, 101],
  [121, 45, 86],
];

// A single canvas, geographic IDW interpolation, clipped to the route corridor.
// Hour changes redraw prefetched data; no network requests on slider interaction.
export default function WeatherHeatmap({ data, hour, visible }) {
  const map = useMap();
  useEffect(() => {
    if (!data?.corridor || !visible) return;
    const pane = map.getPane("weather") || map.createPane("weather");
    pane.style.zIndex = 350;
    pane.style.pointerEvents = "none";
    const canvas = L.DomUtil.create("canvas", "weather-canvas", pane);
    canvas.setAttribute("aria-hidden", "true");
    let frame;
    function draw() {
      const size = map.getSize(),
        origin = map.containerPointToLayerPoint([0, 0]);
      L.DomUtil.setPosition(canvas, origin);
      canvas.width = size.x;
      canvas.height = size.y;
      const ctx = canvas.getContext("2d");
      const center = map.getCenter();
      const kmPx = Math.abs(
        map.latLngToContainerPoint([center.lat + 1 / 111.32, center.lng]).y -
          map.latLngToContainerPoint(center).y,
      );
      const radius = data.corridor.spacing_km * 1.7 * kmPx;
      const points = data.corridor.points.map((p) => ({
        ...map.latLngToContainerPoint([p.lat, p.lon]),
        risk: p.forecast[hour],
      }));
      const step = 5;
      for (let y = 0; y < size.y; y += step)
        for (let x = 0; x < size.x; x += step) {
          let total = 0,
            weighted = 0,
            nearest = Infinity;
          for (const p of points) {
            const d = (p.x - x) ** 2 + (p.y - y) ** 2;
            nearest = Math.min(nearest, d);
            if (d > radius * radius) continue;
            const w = 1 / Math.max(4, d);
            total += w;
            weighted += w * p.risk;
          }
          if (!total || nearest > radius * radius) continue;
          const risk = weighted / total,
            lo = Math.floor(risk),
            hi = Math.min(4, lo + 1),
            f = risk - lo;
          const rgb = palette[lo].map((v, i) =>
            Math.round(v + (palette[hi][i] - v) * f),
          );
          ctx.fillStyle = `rgba(${rgb.join(",")},0.35)`;
          ctx.fillRect(x, y, step, step);
        }
      // Clip interpolation to a true buffered polyline, including the endpoints.
      const mask = document.createElement("canvas");
      mask.width = size.x;
      mask.height = size.y;
      const m = mask.getContext("2d");
      m.strokeStyle = "white";
      m.lineCap = "round";
      m.lineJoin = "round";
      m.lineWidth = data.corridor.width_km * 2 * kmPx;
      for (const route of data.routes) {
        m.beginPath();
        route.geometry.coordinates.forEach(([lon, lat], i) => {
          const p = map.latLngToContainerPoint([lat, lon]);
          i ? m.lineTo(p.x, p.y) : m.moveTo(p.x, p.y);
        });
        m.stroke();
      }
      ctx.globalCompositeOperation = "destination-in";
      ctx.drawImage(mask, 0, 0);
      ctx.globalCompositeOperation = "source-over";
    }
    const schedule = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(draw);
    };
    map.on("moveend zoomend resize", schedule);
    schedule();
    return () => {
      cancelAnimationFrame(frame);
      map.off("moveend zoomend resize", schedule);
      canvas.remove();
    };
  }, [map, data, hour, visible]);
  return null;
}
