import { useEffect, useState } from "react";

type Pair = {
  status: string;
  current: { scene_id: string; acquired_utc: string } | null;
  reference: { scene_id: string; acquired_utc: string } | null;
  days_between: number | null;
  overlap_fraction: number | null;
  class_fractions: { decrease: number | null; stable: number | null; increase: number | null } | null;
  mean_change: number | null;
  low_overlap: boolean;
};
type Resp = { count: number; pairs: Pair[]; note: string };
type Mode = "baseline" | "neighbour";

const URLS: Record<Mode, string> = {
  baseline: "/api/vegetation/change/baseline",
  neighbour: "/api/vegetation/change/series",
};

const pct = (v: number | null | undefined) =>
  v === null || v === undefined ? "n/a" : `${(v * 100).toFixed(1)}%`;
const day = (s: string | undefined) => (s ? s.slice(0, 10) : "?");
const signed = (v: number | null | undefined) =>
  v === null || v === undefined ? "n/a" : `${v > 0 ? "+" : ""}${v}`;

export default function ChangeSeriesPanel() {
  const [mode, setMode] = useState<Mode>("baseline");
  const [data, setData] = useState<Resp | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    const load = async () => {
      try {
        const r = await fetch(URLS[mode]);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const d = (await r.json()) as Resp;
        if (!cancelled) { setData(d); setError(null); }
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      }
    };
    load();
    const id = window.setInterval(load, 300000);
    return () => { cancelled = true; window.clearInterval(id); };
  }, [mode]);

  const th = { textAlign: "left", paddingRight: 14 } as const;
  const td = { paddingRight: 14 } as const;
  const heads =
    mode === "baseline"
      ? ["Baseline", "Scene", "Gap", "Overlap", "Decrease", "Stable", "Increase", "Mean change", ""]
      : ["From", "To", "Gap", "Overlap", "Decrease", "Stable", "Increase", "Mean change", ""];

  return (
    <div style={{ border: "1px solid #1f6f8b", padding: 12, margin: "16px 0", fontSize: 14 }}>
      <strong style={{ color: "#00e5ff" }}>NDVI CHANGE BETWEEN SCENES</strong>
      <label style={{ marginLeft: 12, fontSize: 12 }}>
        Compare:{" "}
        <select value={mode} onChange={(e) => setMode(e.target.value as Mode)}>
          <option value="baseline">every scene vs one baseline</option>
          <option value="neighbour">each scene vs the one before it</option>
        </select>
      </label>
      {error && <p style={{ color: "#ff4500" }}>Could not load: {error}</p>}
      {!data && !error && <p>Loading...</p>}
      {data && data.count === 0 && (
        <p>
          No pairs stored. Run: python -m app.analysis.
          {mode === "baseline" ? "change_baseline" : "change_series"}
        </p>
      )}
      {data && data.count > 0 && (
        <table style={{ fontSize: 12, borderCollapse: "collapse", margin: "8px auto" }}>
          <thead>
            <tr>{heads.map((h) => <th key={h} style={th}>{h}</th>)}</tr>
          </thead>
          <tbody>
            {data.pairs.map((p, i) => (
              <tr key={i} style={{ opacity: p.low_overlap ? 0.5 : 1 }}>
                <td style={td}>{day(p.reference?.acquired_utc)}</td>
                <td style={td}>{day(p.current?.acquired_utc)}</td>
                <td style={td}>{signed(p.days_between)} d</td>
                <td style={td}>{pct(p.overlap_fraction)}</td>
                <td style={td}>{pct(p.class_fractions?.decrease)}</td>
                <td style={td}>{pct(p.class_fractions?.stable)}</td>
                <td style={td}>{pct(p.class_fractions?.increase)}</td>
                <td style={td}>{signed(p.mean_change)}</td>
                <td style={{ color: "#ffb000" }}>
                  {p.low_overlap ? "LOW OVERLAP, do not trust" : ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p style={{ fontSize: 12, margin: "6px 0 0" }}>
        Mean change is the later scene minus the earlier one (scene minus baseline in baseline
        mode); positive means greener. Overlap is the share of pixels usable in both scenes
        (clouds masked). Over gaps of a few days, differences are mostly masking and sensor noise.
        Thresholds are illustrative and NDVI change is not a diagnosis. Contains modified
        Copernicus Sentinel data.
      </p>
    </div>
  );
}
