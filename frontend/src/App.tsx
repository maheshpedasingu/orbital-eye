import AlertsPanel from "./components/AlertsPanel";
import BaselineTrendPanel from "./components/BaselineTrendPanel";
import ChangeSeriesPanel from "./components/ChangeSeriesPanel";
import CorroborationPanel from "./components/CorroborationPanel";
import EarthView from "./components/EarthView";
import MapView from "./components/MapView";
import NdviSeriesPanel from "./components/NdviSeriesPanel";
import PassesPanel from "./components/PassesPanel";
import SatelliteStatePanel from "./components/SatelliteStatePanel";
import SystemStatusPanel from "./components/SystemStatusPanel";

export default function App() {
  return (
    <div style={{ padding: 16 }}>
      <h1>ORBITAL-EYE</h1>
      <SystemStatusPanel />
      <EarthView />
      <SatelliteStatePanel />
      <PassesPanel />
      <AlertsPanel />
      <CorroborationPanel />
      <NdviSeriesPanel />
      <ChangeSeriesPanel />
      <BaselineTrendPanel />
      <h2>Area of interest</h2>
      <MapView />
    </div>
  );
}