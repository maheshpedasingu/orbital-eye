import shutil
import subprocess
from pathlib import Path

import pytest

from app.flight_telemetry import PACKET_SIZE, decode_packet

ROOT = Path(__file__).resolve().parents[2]
GCC = shutil.which("gcc")

pytestmark = pytest.mark.skipif(GCC is None, reason="gcc not found on PATH")

FAULT_BITS = {
    "BATT_LOW": 0x0001, "BATT_CRITICAL": 0x0002, "TEMP_HIGH": 0x0004,
    "TEMP_LOW": 0x0008, "WATCHDOG": 0x0010, "SENSOR_INVALID": 0x0020,
}
CRITICAL_BITS = (FAULT_BITS["BATT_CRITICAL"] | FAULT_BITS["TEMP_HIGH"]
                 | FAULT_BITS["WATCHDOG"] | FAULT_BITS["SENSOR_INVALID"])

# Written by hand from the scenario table, NOT read from the C output.
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
    (6200, "SAFE", ["SENSOR_INVALID"], 8000),  # battery value is the stale last-good one
]
COMMAND_STEPS = {1, 2, 4, 7}  # steps where the scenario sends a command


@pytest.fixture(scope="module")
def stream(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("scenario")
    exe = tmp / "emit_scenario.exe"
    build = subprocess.run(
        [GCC, "-std=c99", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
         f"-I{ROOT / 'flight_core' / 'include'}",
         str(ROOT / "flight_core" / "src" / "telemetry.c"),
         str(ROOT / "flight_core" / "src" / "health.c"),
         str(ROOT / "flight_core" / "tools" / "emit_scenario.c"),
         "-o", str(exe)],
        capture_output=True, text=True)
    assert build.returncode == 0, build.stderr
    out = tmp / "scenario.bin"
    run = subprocess.run([str(exe), str(out)], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr   # also fails if a command result differed
    data = out.read_bytes()
    return [decode_packet(data[i:i + PACKET_SIZE])
            for i in range(0, len(data), PACKET_SIZE)]


def fault_names(flags):
    return sorted(n for n, b in FAULT_BITS.items() if flags & b)


def test_one_packet_per_step(stream):
    assert len(stream) == len(EXPECTED)


def test_every_step_matches_the_hand_written_table(stream):
    for i, (t, mode, faults, batt) in enumerate(EXPECTED):
        p = stream[i]
        assert p["sequence"] == i, f"step {i}"
        assert p["mission_time_ms"] == t, f"step {i}"
        assert p["mode"] == mode, f"step {i}"
        assert fault_names(p["fault_flags"]) == sorted(faults), f"step {i}"
        assert p["battery_mv"] == batt, f"step {i}"
        assert p["temperature_cdeg"] == 2000, f"step {i}"
        assert p["origin"] == "SIMULATED", f"step {i}"


def test_critical_faults_always_mean_safe(stream):
    for i, p in enumerate(stream):
        if p["fault_flags"] & CRITICAL_BITS:
            assert p["mode"] == "SAFE", f"step {i}"


def test_observation_never_coexists_with_a_fault(stream):
    for i, p in enumerate(stream):
        if p["mode"] == "OBSERVATION":
            assert p["fault_flags"] == 0, f"step {i}"


def test_safe_is_only_left_after_a_command(stream):
    left_safe = {i for i in range(1, len(stream))
                 if stream[i - 1]["mode"] == "SAFE" and stream[i]["mode"] != "SAFE"}
    assert left_safe == {1, 7}
    assert left_safe <= COMMAND_STEPS