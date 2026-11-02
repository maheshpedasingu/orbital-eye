import { useEffect, useState } from "react";

type Task = {
  task: string;
  never_run: boolean;
  status: string | null;
  last_attempt_utc: string | null;
  message: string | null;
  last_success_utc: string | null;
  expected_interval_minutes: number;
  overdue: boolean;
};

type Status = {
  generated_utc: string;
  scheduler_running: boolean;
  tasks: Task[];
  fire_detections: { count: number; latest_retrieved_utc: string | null };
};

function ago(iso: string | null, now: string): string {
  if (!iso) return "never";
  const minutes = Math.round((Date.parse(now) - Date.parse(iso)) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 120) return `${minutes} min ago`;
  const hours = minutes / 60;
  return hours < 48 ? `${hours.toFixed(1)} h ago` : `${(hours / 24).toFixed(1)} days ago`;
}

const LABELS: Record<string, string> = {
  firms: "NASA FIRMS fire detections",
  alerts: "Alert evaluation",
  tle: "Orbital elements (CelesTrak)",
  vegetation: "Sentinel-2 NDVI",
  change: "NDVI change",
};

export default function SystemStatusPanel() {
  const [data, setData] = useState<Status | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const r = await fetch("/api/system/status");
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const d = (await r.json()) as Status;
        if (!cancelled) { setData(d); setError(null); }
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      }
    };
    load();
    const id = window.setInterval(load, 60000);
    return () => { cancelled = true; window.clearInterval(id); };
  }, []);

  const colour = (t: Task) =>
    t.status === "failed" ? "#ff4500" : t.overdue ? "#ffb000" : "#7cfc00";

  return (
    <div style={{ border: "1px solid #1f6f8b", padding: 12, margin: "16px 0", fontSize: 14 }}>
      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <strong style={{ color: "#00e5ff" }}>SYSTEM STATUS</strong>
        {data && (
          <span
            style={{
              background: data.scheduler_running ? "#1a6b3a" : "#8a5a00",
              padding: "1px 6px", fontSize: 12,
            }}
          >
            scheduler {data.scheduler_running ? "running" : "not running"}
          </span>
        )}
      </div>

      {error && <p style={{ color: "#ff4500" }}>Could not load status: {error}</p>}
      {!data && !error && <p>Loading...</p>}

      {data && (
        <>
          {data.tasks.map((t) => (
            <div key={t.task} style={{ borderLeft: `4px solid ${colour(t)}`, padding: "2px 10px", margin: "6px 0" }}>
              <div>
                <b>{LABELS[t.task] ?? t.task}</b>:{" "}
                last success {ago(t.last_success_utc, data.generated_utc)}
                {t.overdue ? " (OVERDUE)" : ""}
                {t.status === "failed" ? ", last attempt FAILED" : ""}
                {t.never_run ? " (has never run)" : ""}
              </div>
              {t.status === "failed" && t.message && (
                <div style={{ fontSize: 12, color: "#ff8a65" }}>{t.message}</div>
              )}
            </div>
          ))}
          <p style={{ margin: "8px 0 0" }}>
            Stored fire detections: {data.fire_detections.count}. Last FIRMS data retrieved:{" "}
            {ago(data.fire_detections.latest_retrieved_utc, data.generated_utc)}.
          </p>
          <p style={{ fontSize: 12, margin: "4px 0 0" }}>
            A job is flagged overdue after three times its interval. A successful run can still
            report "no scene" or "0 detections": those are real answers, not errors. Start the
            refresh loop with: python -m app.scheduler --loop-minutes 30
          </p>
        </>
      )}
    </div>
  );
}