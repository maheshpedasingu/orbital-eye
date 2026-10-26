import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { latLonToVector3 } from "../lib/geo";

const EARTH_RADIUS_KM = 6378.137;

type TrackPoint = { t_s: number; lat_deg: number; lon_deg: number; alt_km: number };

export default function EarthView() {
  const mountRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState("Loading ground track...");

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

    let pts: THREE.Vector3[] = [];
    let times: number[] = [];
    const SPEED = 60; // simulated seconds per real second
    let cancelled = false;
    fetch("/api/orbit/ground-track")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data) => {
        if (cancelled) return;
        const track = data.points as TrackPoint[];
        times = track.map((p) => p.t_s);
        pts = track.map((p) =>
          latLonToVector3(p.lat_deg, p.lon_deg, (EARTH_RADIUS_KM + p.alt_km) / EARTH_RADIUS_KM)
        );
        const line = new THREE.Line(
          new THREE.BufferGeometry().setFromPoints(pts),
          new THREE.LineBasicMaterial({ color: 0x00e5ff })
        );
        scene.add(line);
        marker.visible = true;
        setStatus(`${data.data_origin} ground track: ${data.point_count} points`);
      })
      .catch((e) => {
        if (!cancelled) setStatus(`Could not load ground track: ${e.message}`);
      });

    const startTime = performance.now();
    let frameId = 0;
    const animate = () => {
      if (pts.length > 1) {
        const total = times[times.length - 1];
        const t = (((performance.now() - startTime) / 1000) * SPEED) % total;
        const i = Math.min(Math.floor(t / (times[1] - times[0])), pts.length - 2);
        const f = (t - times[i]) / (times[i + 1] - times[i]);
        marker.position.copy(pts[i]).lerp(pts[i + 1], f);
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

  return (
    <div>
      <div ref={mountRef} style={{ width: "100%", height: 500 }} />
      <p>{status}</p>
    </div>
  );
}