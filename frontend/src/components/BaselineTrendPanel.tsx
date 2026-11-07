import { useEffect, useState } from "react";

type Pair = {
  current: { acquired_utc: string } | null;
  reference: { acquired_utc: string } | null;
  mean_change: number | null;
  overlap_fraction: number | null;
  low_overlap: boolean;
};
type Resp = { count: number; pairs: Pair[] };

const W = 640;
const H = 220;
const PAD = { l: 48, r: 16, t: 12, b: 28 };

export default function BaselineTrendPanel() {
  const [data, setData] = useState<Resp | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const r = await fetch("/api/vegetation/change/baseline");
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
  }, []);

  const pts = (data?.pairs ?? [])
    .filter((p) => p.mean_change !== null && p.current)
    .map((p) => ({
      t: Date.parse(p.current!.acquired_utc),
      v: p.mean_change as number,
      low: p.low_overlap,
    }))
    .sort((a, b) => a.t - b.t);
  const baseT = data?.pairs[0]?.reference ? Date.parse(data.pairs[0].reference.acquired_utc) : NaN;
  const all = Number.isFinite(baseT) ? [...pts, { t: baseT, v: 0, low: false }] : pts;

  const tMin = all.length ? Math.min(...all.map((p) => p.t)) : 0;
  const tMax = all.length ? Math.max(...all.map((p) => p.t)) : 1;
  const vMin = Math.min(0, ...all.map((p) => p.v)) - 0.05;
  const vMax = Math.max(0, ...all.map((p) => p.v)) + 0.05;
  const x = (t: number) =>
    tMax === tMin ? (PAD.l + W - PAD.r) / 2 : PAD.l + ((t - tMin) / (tMax - tMin)) * (W - PAD.l - PAD.r);
  const y = (v: number) => PAD.t + (1 - (v - vMin) / (vMax - vMin)) * (H - PAD.t - PAD.b);

  const ok = pts.filter((p) => !p.low);
  const line = ok.map((p) => `${x(p.t)},${y(p.v)}`).join(" ");
  const ticks = [vMin, 0, vMax].map((v) => Math.round(v * 100) / 100);

  return (
    <div style={{ border: "1px solid #1f6f8b", padding: 12, margin: "16px 0", fontSize: 14 }}>
      <strong style={{ color: "#00e5ff" }}>NDVI CHANGE VS BASELINE OVER TIME</strong>
      <span style={{ marginLeft: 12, fontSize: 12 }}>mean NDVI of each scene minus the baseline scene</span>
      {error && <p style={{ color: "#ff4500" }}>Could not load: {error}</p>}
      {!data && !error && <p>Loading...</p>}
      {data && pts.length === 0 && (
        <p>No baseline results. Run: python -m app.analysis.change_baseline</p>
      )}
      {pts.length > 0 && (
        <>
          <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", maxWidth: W, display: "block", margin: "0 auto" }}>
            {ticks.map((v) => (
              <g key={v}>
                <line x1={PAD.l} x2={W - PAD.r} y1={y(v)} y2={y(v)}
                  stroke={v === 0 ? "#9ab" : "#1f3b47"} strokeDasharray={v === 0 ? "4 3" : undefined} />
                <text x={PAD.l - 6} y={y(v) + 4} fontSize="10" fill="#9ab" textAnchor="end">
                  {v > 0 ? "+" : ""}{v}
                </text>
              </g>
            ))}
            <polyline points={line} fill="none" stroke="#7cfc00" strokeWidth="2" />
            {pts.map((p, i) => (
              <circle key={i} cx={x(p.t)} cy={y(p.v)} r="4"
                fill={p.low ? "none" : "#7cfc00"} stroke={p.low ? "#ffb000" : "#7cfc00"} strokeWidth="2" />
            ))}
            {Number.isFinite(baseT) && (
              <circle cx={x(baseT)} cy={y(0)} r="4" fill="#00e5ff" />
            )}
            {[tMin, tMax].map((t, i) => (
              <text key={i} x={x(t)} y={H - 8} fontSize="10" fill="#9ab"
                textAnchor={i === 0 ? "start" : "end"}>
                {new Date(t).toISOString().slice(0, 10)}
              </text>
            ))}
          </svg>
          <p style={{ fontSize: 12, margin: "6px 0 0" }}>
            <span style={{ color: "#00e5ff" }}>&#9679;</span> baseline (zero by definition){" "}
            <span style={{ color: "#7cfc00" }}>&#9679;</span> scene, usable overlap{" "}
            <span style={{ color: "#ffb000" }}>&#9675;</span> low overlap, not joined and not to be trusted.
            Positive means greener than the baseline. Points are placed by acquisition date. One
            baseline date sets every value, so this shows a seasonal pattern, not a diagnosis.
            Contains modified Copernicus Sentinel data.
          </p>
        </>
      )}
    </div>
  );
}
