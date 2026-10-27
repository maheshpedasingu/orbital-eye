import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { latLonToVector3 } from "../lib/geo";

const EARTH_RADIUS_KM = 6378.137;

type TrackPoint = { t_s: number; lat_deg: number; lon_deg: number; alt_km: number };
type Telemetry = TrackPoint & { speed_km_s: number };

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
  const visRef = useRef({ ideal: true, sgp4: true });

  const [idealStatus, setIdealStatus] = useState("Idealized track: loading...");
  const [sgp4Status, setSgp4Status] = useState("SGP4 track: loading...");
  const [telemetry, setTelemetry] = useState<Telemetry | null>(null);
  const [showIdeal, setShowIdeal] = useState(true);
  const [showSgp4, setShowSgp4] = useState(true);

  useEffect(() => {
    visRef.current = { ideal: showIdeal, sgp4: showSgp4 };
    if (idealLineRef.current) idealLineRef.current.visible = showIdeal;
    if (sgp4LineRef.current) sgp4LineRef.current.visible = showSgp4;
  }, [showIdeal, showSgp4]);

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

    let samples: TrackPoint[] = [];
    let pts: THREE.Vector3[] = [];
    let times: number[] = [];
    let speedKmS = 0;
    let lastIndex = -1;
    const SPEED = 60; // simulated seconds per real second

    let cancelled = false;

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
        </div>
      </div>
      <p style={{ margin: "8px 0 0" }}>{idealStatus}</p>
      <p style={{ margin: "4px 0 0" }}>{sgp4Status}</p>
    </div>
  );
}
