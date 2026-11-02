import AlertsPanel from "./components/AlertsPanel";
import EarthView from "./components/EarthView";
import MapView from "./components/MapView";
import PassesPanel from "./components/PassesPanel";
import SystemStatusPanel from "./components/SystemStatusPanel";

export default function App() {
  return (
    <div style={{ padding: 16 }}>
      <h1>ORBITAL-EYE</h1>
      <SystemStatusPanel />
      <EarthView />
      <PassesPanel />
      <AlertsPanel />
      <h2>Area of interest</h2>
      <MapView />
    </div>
  );
}