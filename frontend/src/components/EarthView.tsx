import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { latLonToVector3 } from "../lib/geo";

const EARTH_RADIUS_KM = 6378.137;

type TrackPoint = { t_s: number; lat_deg: number; lon_deg: number; alt_km: number };
type Telemetry = TrackPoint & { speed_km_s: number };
type RealSat = {
  catnr: number;
  name: string;
  purpose?: string;
  status: string;
  message?: string;
  tle_age_days?: number;
  state?: { lat_deg: number; lon_deg: number; alt_km: number };
};

const COLOR_NDVI = 0xff7f50;
const COLOR_FIRE = 0xc792ea;
const colorFor = (s: { purpose?: string }) =>
  s.purpose === "NDVI imagery" ? COLOR_NDVI : COLOR_FIRE;
const hex = (c: number) => "#" + c.toString(16).padStart(6, "0");

function toVectors(points: TrackPoint[]): THREE.Vector3[] {
  return points.map((p) =>
    latLonToVector3(p.lat_deg, p.lon_deg, (EARTH_RADIUS_KM + p.alt_km) / EARTH_RADIUS_KM)
  );
}

function makeLine(pts: THREE.Vector3[], color: number, visible: boolean): THREE.Line {
  const line = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(pts),
    new THREE.LineBasicMaterial({ color })
  );
  line.visible = visible;
  return line;
}

export default function EarthView() {
  const mountRef = useRef<HTMLDivElement>(null);
  const idealLineRef = useRef<THREE.Line | null>(null);
  const sgp4LineRef = useRef<THREE.Line | null>(null);
  const realGroupRef = useRef<THREE.Group | null>(null);
  const visRef = useRef({ ideal: true, sgp4: true, real: true });

  const [idealStatus, setIdealStatus] = useState("Idealized track: loading...");
  const [sgp4Status, setSgp4Status] = useState("SGP4 track: loading...");
  const [realStatus, setRealStatus] = useState("Real satellites: loading...");
  const [realSats, setRealSats] = useState<RealSat[]>([]);
  const [telemetry, setTelemetry] = useState<Telemetry | null>(null);
  const [showIdeal, setShowIdeal] = useState(true);
  const [showSgp4, setShowSgp4] = useState(true);
  const [showReal, setShowReal] = useState(true);

  useEffect(() => {
    visRef.current = { ideal: showIdeal, sgp4: showSgp4, real: showReal };
    if (idealLineRef.current) idealLineRef.current.visible = showIdeal;
    if (sgp4LineRef.current) sgp4LineRef.current.visible = showSgp4;
    if (realGroupRef.current) realGroupRef.current.visible = showReal;
  }, [showIdeal, showSgp4, showReal]);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    const width = mount.clientWidth;
    const height = 500;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
    camera.position.set(0, 0, 3.5);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(width, height);
    mount.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);

    // Earth: radius 1 scene unit = 6378.137 km
    scene.add(
      new THREE.Mesh(
        new THREE.SphereGeometry(1, 48, 32),
        new THREE.MeshBasicMaterial({ color: 0x0b2a4a })
      )
    );
    scene.add(
      new THREE.Mesh(
        new THREE.SphereGeometry(1.001, 24, 16),
        new THREE.MeshBasicMaterial({ color: 0x1f6f8b, wireframe: true })
      )
    );

    const marker = new THREE.Mesh(
      new THREE.SphereGeometry(0.02, 16, 16),
      new THREE.MeshBasicMaterial({ color: 0x7cfc00 })
    );
    marker.visible = false;
    scene.add(marker);

    // Real satellites layer
    const realGroup = new THREE.Group();
    realGroup.visible = visRef.current.real;
    realGroupRef.current = realGroup;
    scene.add(realGroup);
    const markers = new Map<number, THREE.Mesh>();
    const tracked = new Set<number>();

    let samples: TrackPoint[] = [];
    let pts: THREE.Vector3[] = [];
    let times: number[] = [];
    let speedKmS = 0;
    let lastIndex = -1;
    const SPEED = 60; // simulated seconds per real second

    let cancelled = false;

    const loadTrack = async (s: RealSat) => {
      try {
        const r = await fetch(`/api/satellites/${s.catnr}/track?minutes=95&step_s=60`);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const d = await r.json();
        if (cancelled) return;
        const points = (d.points ?? []) as TrackPoint[];
        if (points.length > 1) {
          realGroup.add(makeLine(toVectors(points), colorFor(s), true));
        }
      } catch {
        tracked.delete(s.catnr); // retry on the next refresh
      }
    };

    const loadReal = async () => {
      try {
        const r = await fetch("/api/satellites/state");
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const d = await r.json();
        if (cancelled) return;
        const sats = d.satellites as RealSat[];
        setRealSats(sats);
        let shown = 0;
        for (const s of sats) {
          if (!s.state) continue;
          shown += 1;
          let m = markers.get(s.catnr);
          if (!m) {
            m = new THREE.Mesh(
              new THREE.SphereGeometry(0.025, 16, 16),
              new THREE.MeshBasicMaterial({ color: colorFor(s) })
            );
            markers.set(s.catnr, m);
            realGroup.add(m);
          }
          m.position.copy(
            latLonToVector3(
              s.state.lat_deg,
              s.state.lon_deg,
              (EARTH_RADIUS_KM + s.state.alt_km) / EARTH_RADIUS_KM
            )
          );
          if (!tracked.has(s.catnr)) {
            tracked.add(s.catnr);
            loadTrack(s);
          }
        }
        setRealStatus(
          `${d.data_origin}: ${shown} of ${sats.length} satellites positioned (updates every 10 s)`
        );
      } catch (e) {
        if (!cancelled) setRealStatus(`Real satellites failed: ${(e as Error).message}`);
      }
    };
    loadReal();
    const realTimer = window.setInterval(loadReal, 10000);

    // Idealized circular orbit, same altitude/inclination as the ISS fixture TLE
    fetch("/api/orbit/ground-track?altitude_km=420&inclination_deg=51.6439&step_s=60")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data) => {
        if (cancelled) return;
        samples = data.points as TrackPoint[];
        speedKmS = data.speed_km_s as number;
        times = samples.map((p) => p.t_s);
        pts = toVectors(samples);
        const line = makeLine(pts, 0x00e5ff, visRef.current.ideal);
        idealLineRef.current = line;
        scene.add(line);
        setIdealStatus(`${data.data_origin} idealized track: ${data.point_count} points`);
      })
      .catch((e) => {
        if (!cancelled) setIdealStatus(`Idealized track failed: ${e.message}`);
      });

    // SGP4 track from the built-in test-fixture TLE
    fetch("/api/orbit/tle-ground-track")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data) => {
        if (cancelled) return;
        const line = makeLine(
          toVectors(data.points as TrackPoint[]),
          0xffb000,
          visRef.current.sgp4
        );
        sgp4LineRef.current = line;
        scene.add(line);
        setSgp4Status(
          `${data.data_origin} SGP4 track (${data.orbit_source}): ${data.point_count} points`
        );
      })
      .catch((e) => {
        if (!cancelled) setSgp4Status(`SGP4 track failed: ${e.message}`);
      });

    const startTime = performance.now();
    let frameId = 0;
    const animate = () => {
      marker.visible = pts.length > 1 && visRef.current.ideal;
      if (pts.length > 1) {
        const total = times[times.length - 1];
        const t = (((performance.now() - startTime) / 1000) * SPEED) % total;
        const i = Math.min(Math.floor(t / (times[1] - times[0])), pts.length - 2);
        const f = (t - times[i]) / (times[i + 1] - times[i]);
        marker.position.copy(pts[i]).lerp(pts[i + 1], f);
        if (i !== lastIndex) {
          lastIndex = i;
          setTelemetry({ ...samples[i], speed_km_s: speedKmS });
        }
      }
      controls.update();
      renderer.render(scene, camera);
      frameId = requestAnimationFrame(animate);
    };
    animate();

    return () => {
      cancelled = true;
      window.clearInterval(realTimer);
      cancelAnimationFrame(frameId);
      controls.dispose();
      renderer.dispose();
      mount.removeChild(renderer.domElement);
    };
  }, []);

  const row = { display: "flex", justifyContent: "space-between", gap: 16 } as const;

  return (
    <div>
      <div style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
        <div ref={mountRef} style={{ flex: 1, minWidth: 0, height: 500 }} />
        <div
          style={{
            width: 280,
            padding: 12,
            border: "1px solid #1f6f8b",
            fontFamily: "monospace",
            fontSize: 14,
          }}
        >
          <div style={{ color: "#00e5ff", marginBottom: 8 }}>
            TELEMETRY (SIMULATED, idealized orbit)
          </div>
          {telemetry ? (
            <>
              <div style={row}><span>Sim time</span><span>{telemetry.t_s.toFixed(0)} s</span></div>
              <div style={row}><span>Latitude</span><span>{telemetry.lat_deg.toFixed(2)}&deg;</span></div>
              <div style={row}><span>Longitude</span><span>{telemetry.lon_deg.toFixed(2)}&deg;</span></div>
              <div style={row}><span>Altitude</span><span>{telemetry.alt_km.toFixed(1)} km</span></div>
              <div style={row}><span>Speed</span><span>{telemetry.speed_km_s.toFixed(3)} km/s</span></div>
            </>
          ) : (
            <div>Waiting for data...</div>
          )}

          <div style={{ color: "#00e5ff", margin: "16px 0 8px" }}>LAYERS</div>
          <label style={{ display: "block", color: "#00e5ff" }}>
            <input
              type="checkbox"
              checked={showIdeal}
              onChange={(e) => setShowIdeal(e.target.checked)}
            />{" "}
            Idealized circular orbit
          </label>
          <label style={{ display: "block", color: "#ffb000" }}>
            <input
              type="checkbox"
              checked={showSgp4}
              onChange={(e) => setShowSgp4(e.target.checked)}
            />{" "}
            SGP4 (fixture TLE, Dec 2019)
          </label>
          <label style={{ display: "block", color: hex(COLOR_FIRE) }}>
            <input
              type="checkbox"
              checked={showReal}
              onChange={(e) => setShowReal(e.target.checked)}
            />{" "}
            Real satellites (current TLE)
          </label>

          {realSats.length > 0 && (
            <div style={{ marginTop: 10, fontSize: 12 }}>
              {realSats.map((s) => (
                <div key={s.catnr} style={{ color: hex(colorFor(s)) }}>
                  &#9632; {s.name}
                  {s.state
                    ? ` (${s.state.alt_km.toFixed(0)} km)`
                    : ` (${s.status})`}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
      <p style={{ margin: "8px 0 0" }}>{idealStatus}</p>
      <p style={{ margin: "4px 0 0" }}>{sgp4Status}</p>
      <p style={{ margin: "4px 0 0" }}>{realStatus}</p>
      <p style={{ margin: "4px 0 0", fontSize: 12 }}>
        Real satellites: markers are the current position, lines are the next 95 minutes of
        ground track. Both are propagated from real CelesTrak element sets and lose accuracy as
        the element set ages. Coral = Sentinel-2, purple = VIIRS fire satellites.
      </p>
    </div>
  );
}
