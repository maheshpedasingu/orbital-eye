import shutil
import subprocess
from pathlib import Path

import pytest

from app.flight_telemetry import PACKET_SIZE, decode_packet

ROOT = Path(__file__).resolve().parents[2]
FLIGHT = ROOT / "flight_core"
GCC = shutil.which("gcc")

pytestmark = pytest.mark.skipif(GCC is None, reason="gcc not found on PATH")

FAULT_BITS = {
    "BATT_LOW": 0x0001, "BATT_CRITICAL": 0x0002, "TEMP_HIGH": 0x0004,
    "TEMP_LOW": 0x0008, "WATCHDOG": 0x0010, "SENSOR_INVALID": 0x0020,
}

# Same hand-written table as test_health_scenario.py.
# (mission time ms, mode, active faults, battery mV)
EXPECTED = [
    (100, "SAFE", [], 8000),
    (200, "NOMINAL", [], 8000),
    (300, "OBSERVATION", [], 8000),
    (400, "NOMINAL", ["BATT_LOW"], 6900),
    (500, "SAFE", ["BATT_CRITICAL", "BATT_LOW"], 6700),
    (600, "SAFE", ["BATT_LOW"], 7000),
    (700, "SAFE", [], 7400),
    (800, "NOMINAL", [], 8000),
    (6000, "SAFE", ["WATCHDOG"], 8000),
    (6100, "SAFE", [], 8000),
    (6200, "SAFE", ["SENSOR_INVALID"], 8000),
]


def build_and_run(tmp, tool, sources, name):
    exe = tmp / f"{name}.exe"
    build = subprocess.run(
        [GCC, "-std=c99", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
         f"-I{FLIGHT / 'include'}",
         *[str(FLIGHT / "src" / s) for s in sources],
         str(FLIGHT / "tools" / tool), "-o", str(exe)],
        capture_output=True, text=True)
    assert build.returncode == 0, build.stderr
    out = tmp / f"{name}.bin"
    run = subprocess.run([str(exe), str(out)], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    return out.read_bytes()


@pytest.fixture(scope="module")
def outputs(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("hal_scenario")
    direct = build_and_run(tmp, "emit_scenario.c", ["telemetry.c", "health.c"], "direct")
    via_hal = build_and_run(
        tmp, "emit_hal_scenario.c",
        ["telemetry.c", "health.c", "hal.c", "hal_sim.c", "monitor.c"], "hal")
    return direct, via_hal


def fault_names(flags):
    return sorted(n for n, b in FAULT_BITS.items() if flags & b)


def test_hal_driven_run_is_byte_identical_to_the_direct_run(outputs):
    direct, via_hal = outputs
    assert len(direct) == len(EXPECTED) * PACKET_SIZE
    assert via_hal == direct


def test_hal_driven_run_matches_the_hand_written_table(outputs):
    _, via_hal = outputs
    packets = [decode_packet(via_hal[i:i + PACKET_SIZE])
               for i in range(0, len(via_hal), PACKET_SIZE)]
    assert len(packets) == len(EXPECTED)
    for i, (t, mode, faults, batt) in enumerate(EXPECTED):
        p = packets[i]
        assert p["mission_time_ms"] == t, f"step {i}"
        assert p["mode"] == mode, f"step {i}"
        assert fault_names(p["fault_flags"]) == sorted(faults), f"step {i}"
        assert p["battery_mv"] == batt, f"step {i}"
        assert p["origin"] == "SIMULATED", f"step {i}"