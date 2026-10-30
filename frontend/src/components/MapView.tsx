import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

type TrackPoint = { t_s: number; lat_deg: number; lon_deg: number; alt_km: number };

type FireProps = {
  data_origin: string;
  status: string;
  source: string;
  satellite: string | null;
  acquired_utc: string;
  retrieved_utc: string;
  confidence_raw: string | null;
  frp_mw: number | null;
  daynight: string | null;
  distance_to_aoi_centre_km: number;
  inside_aoi_box: boolean;
};

function esc(value: unknown): string {
  const map: Record<string, string> = {
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  };
  return String(value ?? "unknown").replace(/[&<>"']/g, (c) => map[c]);
}

// Split a track wherever it crosses the +/-180 degree longitude line
function splitAtAntimeridian(points: TrackPoint[]): L.LatLngTuple[][] {
  const segments: L.LatLngTuple[][] = [[]];
  points.forEach((p, i) => {
    if (i > 0 && Math.abs(p.lon_deg - points[i - 1].lon_deg) > 180) segments.push([]);
    segments[segments.length - 1].push([p.lat_deg, p.lon_deg]);
  });
  return segments;
}

async function getJson(url: string) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export default function MapView() {
  const mapDivRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState("Loading map data...");

  useEffect(() => {
    const el = mapDivRef.current;
    if (!el) return;

    const map = L.map(el).setView([16.506, 80.648], 7);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map);

    const layers = L.control.layers().addTo(map);
    let cancelled = false;
    let timer: number | undefined;
    const messages: string[] = [];

    const aoiRequest = getJson("/api/aoi")
      .then((data) => {
        if (cancelled) return;
        const layer = L.geoJSON(data.aoi, {
          style: { color: "#00e5ff", weight: 2, fillOpacity: 0.1 },
          onEachFeature: (f, l) =>
            l.bindPopup(`${esc(f.properties.name)}<br/>${esc(f.properties.note)}`),
        }).addTo(map);
        layers.addOverlay(layer, "Area of interest");
        messages.push(`${data.data_origin} AOI`);
      })
      .catch((e) => messages.push(`AOI failed: ${e.message}`));

    const trackRequest = Promise.all([
      getJson("/api/orbit/tle-ground-track"),
      getJson("/api/orbit/footprint?altitude_km=420&min_elevation_deg=0"),
    ])
      .then(([track, fp]) => {
        if (cancelled) return;
        const pts = track.points as TrackPoint[];

        const line = L.polyline(splitAtAntimeridian(pts), {
          color: "#ffb000",
          weight: 2,
        }).addTo(map);
        line.bindPopup(`SGP4 track (${esc(track.orbit_source)}). ${esc(track.warning)}`);
        layers.addOverlay(line, "SGP4 ground track (fixture TLE)");

        const footprint = L.circle([pts[0].lat_deg, pts[0].lon_deg], {
          radius: fp.radius_km * 1000, // km -> m
          color: "#7cfc00",
          weight: 1,
          fillOpacity: 0.08,
        }).addTo(map);
        footprint.bindPopup("Horizon-limited visibility circle (not a camera swath)");
        layers.addOverlay(footprint, "Visibility footprint");

        let i = 0;
        timer = window.setInterval(() => {
          i = (i + 1) % pts.length;
          footprint.setLatLng([pts[i].lat_deg, pts[i].lon_deg]);
        }, 1000);

        messages.push(`${track.data_origin} SGP4 track`);
      })
      .catch((e) => messages.push(`Track failed: ${e.message}`));

    const fireRequest = getJson("/api/fires?days=3")
      .then((data) => {
        if (cancelled) return;
        const layer = L.geoJSON(data, {
          pointToLayer: (_f, latlng) =>
            L.circleMarker(latlng, {
              radius: 7,
              color: "#ff4500",
              weight: 2,
              fillColor: "#ff4500",
              fillOpacity: 0.5,
            }),
          onEachFeature: (f, l) => {
            const p = f.properties as FireProps;
            l.bindPopup(
              `<b>Thermal anomaly (unconfirmed)</b><br/>` +
                `Origin: ${esc(p.data_origin)}<br/>` +
                `Source: ${esc(p.source)} (${esc(p.satellite)})<br/>` +
                `Acquired: ${esc(p.acquired_utc)}<br/>` +
                `Retrieved: ${esc(p.retrieved_utc)}<br/>` +
                `Confidence (raw): ${esc(p.confidence_raw)}<br/>` +
                `FRP: ${esc(p.frp_mw)} MW<br/>` +
                `Day/night: ${esc(p.daynight)}<br/>` +
                `Distance to AOI centre: ${esc(p.distance_to_aoi_centre_km)} km<br/>` +
                `Inside AOI box: ${p.inside_aoi_box ? "yes" : "no"}`
            );
          },
        }).addTo(map);
        layers.addOverlay(layer, "FIRMS thermal anomalies (REAL_EXTERNAL)");
        messages.push(
          `${data.data_origin} FIRMS: ${data.count} detection(s) in last 3 days, ` +
            `last successful retrieval ${data.last_successful_retrieval_utc ?? "never"}`
        );
        if (data.last_run_status === "failed") {
          messages.push(`LAST FIRMS RUN FAILED: ${data.last_run_error}`);
        }
      })
      .catch((e) => messages.push(`Fires failed: ${e.message}`));

    Promise.all([aoiRequest, trackRequest, fireRequest]).then(() => {
      if (!cancelled) setStatus(messages.join(" | "));
    });

    return () => {
      cancelled = true;
      if (timer !== undefined) window.clearInterval(timer);
      map.remove();
    };
  }, []);

  return (
    <div>
      <div ref={mapDivRef} style={{ height: 450, width: "100%" }} />
      <p style={{ margin: "8px 0 0" }}>{status}</p>
    </div>
  );
}
