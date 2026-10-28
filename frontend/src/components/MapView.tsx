import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

export default function MapView() {
  const mapDivRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState("Loading area of interest...");

  useEffect(() => {
    const el = mapDivRef.current;
    if (!el) return;

    const map = L.map(el).setView([16.506, 80.648], 9);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map);

    let cancelled = false;
    fetch("/api/aoi")
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
        map.fitBounds(layer.getBounds().pad(0.3));
        setStatus(`${data.data_origin}: area of interest loaded`);
      })
      .catch((e) => {
        if (!cancelled) setStatus(`Could not load AOI: ${e.message}`);
      });

    return () => {
      cancelled = true;
      map.remove();
    };
  }, []);

  return (
    <div>
      <div ref={mapDivRef} style={{ height: 400, width: "100%" }} />
      <p style={{ margin: "8px 0 0" }}>{status}</p>
    </div>
  );
}
