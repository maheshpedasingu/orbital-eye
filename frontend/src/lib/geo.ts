import * as THREE from "three";

/** lat/lon in degrees, radius in any unit. Returns a Three.js position (y is up). */
export function latLonToVector3(
  latDeg: number,
  lonDeg: number,
  radius: number
): THREE.Vector3 {
  const lat = (latDeg * Math.PI) / 180; // degrees -> radians
  const lon = (lonDeg * Math.PI) / 180;

  const x = radius * Math.cos(lat) * Math.cos(lon);
  const y = radius * Math.sin(lat);
  const z = -radius * Math.cos(lat) * Math.sin(lon);

  return new THREE.Vector3(x, y, z);
}