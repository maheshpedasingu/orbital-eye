import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

type TrackPoint = { t_s: number; lat_deg: number; lon_deg: number; alt_km: number };

// Split a track wherever it crosses the +/-180 degree longitude line
function splitAtAntimeridian(points: TrackPoint[]): L.LatLngTuple[][] {
  const segments: L.LatLngTuple[][] = [[]];
  points.forEach((p, i) => {
    if (i > 0 && Math.abs(p.lon_deg - points[i - 1].lon_deg) > 180) segments.push([]);
    segments[segments.length - 1].push([p.lat_deg, p.lon_deg]);
  });
  return segments;
}

export default function MapView() {
  const mapDivRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState("Loading map data...");

  useEffect(() => {
    const el = mapDivRef.current;
    if (!el) return;

    const map = L.map(el).setView([16.506, 80.648], 3);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map);

    const layers = L.control.layers().addTo(map);
    let cancelled = false;
    let timer: number | undefined;
    const messages: string[] = [];

    const aoiRequest = fetch("/api/aoi")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data) => {
        if (cancelled) return;
        const layer = L.geoJSON(data.aoi, {
          style: { color: "#00e5ff", weight: 2, fillOpacity: 0.1 },
          onEachFeature: (f, l) =>
            l.bindPopup(`${f.properties.name}<br/>${f.properties.note}`),
        }).addTo(map);
        layers.addOverlay(layer, "Area of interest");
        messages.push(`${data.data_origin} AOI`);
      })
      .catch((e) => messages.push(`AOI failed: ${e.message}`));

    const trackRequest = Promise.all([
      fetch("/api/orbit/tle-ground-track").then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      }),
      fetch("/api/orbit/footprint?altitude_km=420&min_elevation_deg=0").then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      }),
    ])
      .then(([track, fp]) => {
        if (cancelled) return;
        const pts = track.points as TrackPoint[];

        const line = L.polyline(splitAtAntimeridian(pts), {
          color: "#ffb000",
          weight: 2,
        }).addTo(map);
        line.bindPopup(`SGP4 track (${track.orbit_source}). ${track.warning}`);
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

        messages.push(`${track.data_origin} SGP4 track, footprint ${fp.radius_km.toFixed(0)} km`);
      })
      .catch((e) => messages.push(`Track failed: ${e.message}`));

    Promise.all([aoiRequest, trackRequest]).then(() => {
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
