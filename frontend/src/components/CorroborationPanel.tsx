import { useEffect, useState } from "react";

type Cluster = {
  satellites: string[];
  detection_ids: number[];
  n_detections: number;
  latitude_deg: number;
  longitude_deg: number;
  first_acquired_utc: string;
  last_acquired_utc: string;
  span_minutes: number;
  distance_to_aoi_centre_km: number;
  data_origin: string;
};

type Corroborated = {
  count: number;
  radius_km: number;
  window_minutes: number;
  clusters: Cluster[];
  note: string;
};

export default function CorroborationPanel() {
  const [data, setData] = useState<Corroborated | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const r = await fetch("/api/fires/corroborated?days=7");
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const d = (await r.json()) as Corroborated;
        if (!cancelled) { setData(d); setError(null); }
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      }
    };
    load();
    const id = window.setInterval(load, 60000);
    return () => { cancelled = true; window.clearInterval(id); };
  }, []);

  return (
    <div style={{ border: "1px solid #1f6f8b", padding: 12, margin: "16px 0", fontSize: 14 }}>
      <strong style={{ color: "#00e5ff" }}>MULTI-SATELLITE CORROBORATION</strong>
      <span style={{ marginLeft: 12, fontSize: 12 }}>last 7 days</span>

      {error && <p style={{ color: "#ff4500" }}>Could not load: {error}</p>}
      {!data && !error && <p>Loading...</p>}
      {data && data.count === 0 && (
        <p>
          No detection has been reported by two or more satellites within{" "}
          {data.radius_km} km and {data.window_minutes} min. This is a real answer,
          not an error.
        </p>
      )}
      {data && data.clusters.map((c) => (
        <div
          key={c.detection_ids.join("-")}
          style={{ borderLeft: "4px solid #ffb000", padding: "2px 10px", margin: "6px 0" }}
        >
          <div>
            <b>Seen by {c.satellites.length} satellites</b>: {c.satellites.join(", ")}
            {" "}({c.n_detections} detections, {c.data_origin})
          </div>
          <div style={{ fontSize: 12 }}>
            {c.latitude_deg.toFixed(3)}, {c.longitude_deg.toFixed(3)},{" "}
            {c.distance_to_aoi_centre_km} km from the AOI centre. First{" "}
            {c.first_acquired_utc.slice(0, 16)} UTC, last {c.last_acquired_utc.slice(0, 16)} UTC
            (span {c.span_minutes} min).
          </div>
        </div>
      ))}
      <p style={{ fontSize: 12, margin: "6px 0 0" }}>
        UNCONFIRMED: several satellites seeing heat raises confidence but does not
        verify a wildfire.
      </p>
    </div>
  );
}
