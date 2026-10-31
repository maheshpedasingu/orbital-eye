import { useEffect, useRef, useState } from "react";

type Alert = {
  id: number;
  created_utc: string;
  severity: "INFO" | "WARNING" | "CRITICAL";
  data_origin: string;
  title: string;
  message: string;
  zone: string;
  distance_km: number;
  acquired_utc: string;
  duplicate_count: number;
};

const COLORS = { INFO: "#4fc3f7", WARNING: "#ffb000", CRITICAL: "#ff4500" } as const;

async function load(origin: "real" | "simulated"): Promise<Alert[]> {
  const r = await fetch(`/api/alerts?origin=${origin}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const data = await r.json();
  return data.alerts as Alert[];
}

export default function AlertsPanel() {
  const [real, setReal] = useState<Alert[]>([]);
  const [sim, setSim] = useState<Alert[]>([]);
  const [showSim, setShowSim] = useState(false);
  const [notifyOn, setNotifyOn] = useState(false);
  const [notifyMsg, setNotifyMsg] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [checked, setChecked] = useState("never");

  const seen = useRef<Set<string> | null>(null);
  const showSimRef = useRef(false);
  const notifyRef = useRef(false);
  useEffect(() => { showSimRef.current = showSim; }, [showSim]);
  useEffect(() => { notifyRef.current = notifyOn; }, [notifyOn]);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const [r, s] = await Promise.all([load("real"), load("simulated")]);
        if (cancelled) return;
        const all = [...r, ...s];
        if (seen.current === null) {
          // First load: remember what exists, do not notify for old alerts
          seen.current = new Set(all.map((a) => `${a.data_origin}-${a.id}`));
        } else {
          for (const a of all) {
            const key = `${a.data_origin}-${a.id}`;
            if (seen.current.has(key)) continue;
            seen.current.add(key);
            const allowed = a.data_origin === "REAL_EXTERNAL" || showSimRef.current;
            if (allowed && notifyRef.current && "Notification" in window &&
                Notification.permission === "granted") {
              new Notification(a.title, { body: a.message });
            }
          }
        }
        setReal(r);
        setSim(s);
        setError(null);
        setChecked(new Date().toISOString());
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      }
    };
    tick();
    const id = window.setInterval(tick, 60000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  const enableNotifications = async () => {
    if (!("Notification" in window)) {
      setNotifyMsg("This browser does not support notifications.");
      return;
    }
    const permission = await Notification.requestPermission();
    setNotifyOn(permission === "granted");
    setNotifyMsg(permission === "granted" ? "Notifications on." : `Permission: ${permission}`);
  };

  const visible = (showSim ? [...real, ...sim] : real).sort((a, b) =>
    b.created_utc.localeCompare(a.created_utc)
  );

  return (
    <div style={{ border: "1px solid #1f6f8b", padding: 12, margin: "16px 0" }}>
      <div style={{ display: "flex", gap: 16, alignItems: "center", flexWrap: "wrap" }}>
        <strong style={{ color: "#00e5ff" }}>ALERTS</strong>
        <label>
          <input type="checkbox" checked={showSim} onChange={(e) => setShowSim(e.target.checked)} />{" "}
          Show simulated test events
        </label>
        <button onClick={enableNotifications}>Enable browser notifications</button>
        <span>{notifyMsg}</span>
      </div>

      {error && <p style={{ color: "#ff4500" }}>Could not load alerts: {error}</p>}

      {visible.length === 0 ? (
        <p>
          No alerts in the history. This means no stored detection has met the alert
          rules. It does not mean there is no fire.
        </p>
      ) : (
        visible.map((a) => (
          <div
            key={`${a.data_origin}-${a.id}`}
            style={{ borderLeft: `4px solid ${COLORS[a.severity]}`, padding: "6px 10px", margin: "8px 0" }}
          >
            <div>
              <strong style={{ color: COLORS[a.severity] }}>{a.severity}</strong>{" "}
              {a.data_origin === "SIMULATED" ? (
                <span style={{ background: "#7a3e9d", padding: "1px 6px" }}>SIMULATED</span>
              ) : (
                <span style={{ background: "#1f6f8b", padding: "1px 6px" }}>REAL_EXTERNAL</span>
              )}{" "}
              {a.zone} zone, {a.distance_km} km from AOI centre
              {a.duplicate_count > 0 ? `, ${a.duplicate_count} repeat detection(s) merged` : ""}
            </div>
            <div style={{ fontSize: 13 }}>{a.message}</div>
          </div>
        ))
      )}

      <p style={{ fontSize: 12, margin: "8px 0 0" }}>
        Alerts last checked (UTC): {checked}. The panel reads stored data and refreshes every
        60 s; it does not fetch from NASA by itself.
      </p>
    </div>
  );
}
