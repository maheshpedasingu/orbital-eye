import { useEffect, useState } from "react";

type Point = {
  scene_id: string;
  acquired_utc: string | null;
  decimate: number;
  metrics: Record<string, number>;
  category_fractions: Record<string, number>;
};

type Series = { count: number; points: Point[] };

const PALETTE = ["#7cfc00", "#ffb000", "#ff4500", "#00e5ff", "#c792ea", "#f78c6c"];
const W = 640;
const H = 220;
const PAD = { l: 44, r: 16, t: 12, b: 28 };

export default function NdviSeriesPanel() {
  const [data, setData] = useState<Series | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const r = await fetch("/api/vegetation/series");
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const d = (await r.json()) as Series;
        if (!cancelled) { setData(d); setError(null); }
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      }
    };
    load();
    const id = window.setInterval(load, 300000);
    return () => { cancelled = true; window.clearInterval(id); };
  }, []);

  const points = data?.points ?? [];
  const names = Array.from(new Set(points.flatMap((p) => Object.keys(p.category_fractions))));
  const x = (i: number) =>
    points.length < 2
      ? (PAD.l + W - PAD.r) / 2
      : PAD.l + (i / (points.length - 1)) * (W - PAD.l - PAD.r);
  const y = (v: number) => PAD.t + (1 - v) * (H - PAD.t - PAD.b);

  const line = (values: (number | undefined)[]) =>
    values
      .map((v, i) => (v === undefined ? null : `${x(i)},${y(v)}`))
      .filter((s): s is string => s !== null)
      .join(" ");

  const series = [
    ...names.map((n, k) => ({
      label: n,
      color: PALETTE[k % PALETTE.length],
      dash: undefined as string | undefined,
      values: points.map((p) => p.category_fractions[n]),
    })),
    {
      label: "scene coverage (fraction with NDVI)",
      color: "#ffffff",
      dash: "4 3",
      values: points.map((p) => p.metrics["fraction_with_ndvi"]),
    },
  ];

  return (
    <div style={{ border: "1px solid #1f6f8b", padding: 12, margin: "16px 0", fontSize: 14 }}>
      <strong style={{ color: "#00e5ff" }}>NDVI TIME SERIES</strong>
      <span style={{ marginLeft: 12, fontSize: 12 }}>
        Sentinel-2, one point per stored real scene
      </span>

      {error && <p style={{ color: "#ff4500" }}>Could not load series: {error}</p>}
      {!data && !error && <p>Loading...</p>}
      {data && points.length === 0 && (
        <p>No NDVI scenes stored yet. Run: python -m app.analysis.vegetation_job</p>
      )}

      {points.length > 0 && (
        <>
          <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", maxWidth: W, display: "block" }}>
            {[0, 0.25, 0.5, 0.75, 1].map((g) => (
              <g key={g}>
                <line x1={PAD.l} x2={W - PAD.r} y1={y(g)} y2={y(g)} stroke="#1f3b47" />
                <text x={PAD.l - 6} y={y(g) + 4} fontSize="10" fill="#9ab" textAnchor="end">
                  {Math.round(g * 100)}%
                </text>
              </g>
            ))}
            {series.map((s) => (
              <g key={s.label}>
                <polyline
                  points={line(s.values)}
                  fill="none"
                  stroke={s.color}
                  strokeWidth="2"
                  strokeDasharray={s.dash}
                />
                {s.values.map((v, i) =>
                  v === undefined ? null : (
                    <circle key={i} cx={x(i)} cy={y(v)} r="3.5" fill={s.color} />
                  ),
                )}
              </g>
            ))}
            {points.map((p, i) => (
              <text key={p.scene_id} x={x(i)} y={H - 8} fontSize="10" fill="#9ab" textAnchor="middle">
                {p.acquired_utc ? p.acquired_utc.slice(0, 10) : "?"}
              </text>
            ))}
          </svg>

          <div style={{ display: "flex", gap: 14, flexWrap: "wrap", fontSize: 12, margin: "6px 0" }}>
            {series.map((s) => (
              <span key={s.label}>
                <span style={{ color: s.color }}>&#9632;</span> {s.label}
              </span>
            ))}
          </div>

          <table style={{ fontSize: 12, borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th style={{ textAlign: "left", paddingRight: 16 }}>Acquired (UTC)</th>
                <th style={{ textAlign: "left", paddingRight: 16 }}>Coverage</th>
                <th style={{ textAlign: "left" }}>Scene</th>
              </tr>
            </thead>
            <tbody>
              {points.map((p) => (
                <tr key={p.scene_id}>
                  <td style={{ paddingRight: 16 }}>{p.acquired_utc ?? "unknown"}</td>
                  <td style={{ paddingRight: 16 }}>
                    {p.metrics["fraction_with_ndvi"] !== undefined
                      ? `${(p.metrics["fraction_with_ndvi"] * 100).toFixed(1)}%`
                      : "n/a"}
                  </td>
                  <td>{p.scene_id}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {points.length === 1 && (
            <p style={{ fontSize: 12 }}>Only one scene is stored, so there is no trend yet.</p>
          )}
          <p style={{ fontSize: 12, margin: "6px 0 0" }}>
            Contains modified Copernicus Sentinel data. Points are spaced evenly, not by date.
            Differences in coverage between scenes limit how far trends can be trusted.
          </p>
        </>
      )}
    </div>
  );
}
