import { useEffect, useState } from "react";

type Opp = {
  start_utc: string;
  end_utc: string;
  tca_utc: string;
  min_distance_km: number;
  local_solar_hour_at_aoi: number;
  daytime: boolean;
  partial: boolean;
};

type Sat = {
  catnr: number;
  name: string;
  instrument: string;
  purpose: string;
  half_swath_km: number;
  daylight_only: boolean;
  status: string;
  message?: string;
  tle_epoch_utc?: string;
  tle_age_days?: number;
  opportunities: Opp[];
};

type Data = {
  data_origin: string;
  generated_utc: string;
  hours: number;
  note: string;
  target: { name: string };
  satellites: Sat[];
};

function fmt(iso: string): string {
  const d = new Date(iso);
  const utc = d.toISOString().slice(0, 16).replace("T", " ") + " UTC";
  const ist = d.toLocaleString("en-IN", {
    timeZone: "Asia/Kolkata", hour12: false,
    day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
  });
  return `${utc} (${ist} IST)`;
}

export default function PassesPanel() {
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const r = await fetch("/api/passes/next?hours=72&limit=4");
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const d = (await r.json()) as Data;
        if (!cancelled) { setData(d); setError(null); }
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      }
    };
    load();
    const id = window.setInterval(load, 600000); // every 10 minutes
    return () => { cancelled = true; window.clearInterval(id); };
  }, []);

  return (
    <div style={{ border: "1px solid #1f6f8b", padding: 12, margin: "16px 0" }}>
      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <strong style={{ color: "#00e5ff" }}>NEXT OBSERVATION OPPORTUNITIES</strong>
        <span style={{ background: "#7a3e9d", padding: "1px 6px", fontSize: 12 }}>
          PROPAGATED_FROM_REAL_TLE
        </span>
      </div>
      {error && <p style={{ color: "#ff4500" }}>Could not load predictions: {error}</p>}
      {!data && !error && <p>Calculating...</p>}
      {data && (
        <>
          {data.satellites.map((s) => (
            <div key={s.catnr} style={{ margin: "10px 0" }}>
              <div>
                <b>{s.name}</b>: {s.instrument}. {s.purpose}.{" "}
                {s.tle_age_days !== undefined && (
                  <span style={{ fontSize: 12 }}>
                    Element set {s.tle_age_days.toFixed(1)} days old.
                  </span>
                )}
              </div>
              {s.status !== "ok" && <div style={{ color: "#ffb000" }}>{s.message}</div>}
              {s.status === "ok" && s.opportunities.length === 0 && (
                <div>
                  No opportunity in the next {data.hours} hours
                  {s.daylight_only ? " (daytime only)" : ""}. This is a prediction, not a gap in data.
                </div>
              )}
              {s.opportunities.map((o) => (
                <div key={o.tca_utc} style={{ fontSize: 13, marginLeft: 12 }}>
                  Closest at {fmt(o.tca_utc)}, {o.min_distance_km} km from the AOI centre
                  (local solar time {o.local_solar_hour_at_aoi.toFixed(1)} h
                  {o.daytime ? ", day" : ", night"}){o.partial ? ", window already open or cut off" : ""}
                </div>
              ))}
            </div>
          ))}
          <p style={{ fontSize: 12, margin: "8px 0 0" }}>{data.note}</p>
        </>
      )}
    </div>
  );
}