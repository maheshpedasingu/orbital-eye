import { useEffect, useState } from "react";

type State = {
  lat_deg: number; lon_deg: number; alt_km: number; speed_km_s: number;
  argument_of_latitude_deg: number | null; ascending: boolean;
};
type Sat = {
  catnr: number; name: string; status: string; message?: string;
  tle_age_days?: number; state?: State;
};
type Resp = { generated_utc: string; note: string; satellites: Sat[] };

export default function SatelliteStatePanel() {
  const [data, setData] = useState<Resp | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const r = await fetch("/api/satellites/state");
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const d = (await r.json()) as Resp;
        if (!cancelled) { setData(d); setError(null); }
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      }
    };
    load();
    const id = window.setInterval(load, 10000);
    return () => { cancelled = true; window.clearInterval(id); };
  }, []);

  return (
    <div style={{ border: "1px solid #1f6f8b", padding: 12, margin: "16px 0", fontSize: 14 }}>
      <strong style={{ color: "#00e5ff" }}>REAL SATELLITES NOW</strong>
      <span style={{ marginLeft: 12, fontSize: 12 }}>PROPAGATED_FROM_REAL_TLE, refreshes every 10 s</span>
      {error && <p style={{ color: "#ff4500" }}>Could not load: {error}</p>}
      {!data && !error && <p>Loading...</p>}
      {data && (
        <table style={{ fontSize: 12, borderCollapse: "collapse", margin: "8px auto" }}>
          <thead>
            <tr>
              {["Satellite", "Lat", "Lon", "Alt km", "km/s", "Phase", "Element age"].map((h) => (
                <th key={h} style={{ textAlign: "left", paddingRight: 14 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.satellites.map((s) => (
              <tr key={s.catnr}>
                <td style={{ paddingRight: 14 }}><b>{s.name}</b></td>
                {s.state ? (
                  <>
                    <td style={{ paddingRight: 14 }}>{s.state.lat_deg.toFixed(2)}</td>
                    <td style={{ paddingRight: 14 }}>{s.state.lon_deg.toFixed(2)}</td>
                    <td style={{ paddingRight: 14 }}>{s.state.alt_km.toFixed(0)}</td>
                    <td style={{ paddingRight: 14 }}>{s.state.speed_km_s.toFixed(2)}</td>
                    <td style={{ paddingRight: 14 }}>
                      {s.state.argument_of_latitude_deg === null
                        ? "n/a" : `${s.state.argument_of_latitude_deg.toFixed(0)}\u00b0`}
                      {s.state.ascending ? " \u2191" : " \u2193"}
                    </td>
                    <td>{s.tle_age_days} d</td>
                  </>
                ) : (
                  <td colSpan={6} style={{ color: "#ffb000" }}>{s.status}: {s.message}</td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p style={{ fontSize: 12, margin: "6px 0 0" }}>
        Computed with SGP4 from real CelesTrak element sets; accuracy drops as the element set
        ages. Phase is the angle from the ascending node (0 = ascending node, 90 = northernmost).
      </p>
    </div>
  );
}
