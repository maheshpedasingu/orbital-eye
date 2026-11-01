import shutil
import subprocess
from pathlib import Path

import pytest

from app.flight_telemetry import PACKET_SIZE, decode_packet

ROOT = Path(__file__).resolve().parents[2]
GCC = shutil.which("gcc")

pytestmark = pytest.mark.skipif(GCC is None, reason="gcc not found on PATH")

EXPECTED = [
    {"sequence": 0x0102, "mission_time_ms": 0x0A0B0C0D, "battery_mv": 8000,
     "temperature_cdeg": -250, "mode": "NOMINAL", "fault_flags": 0x0003,
     "origin": "SIMULATED"},
    {"sequence": 0, "mission_time_ms": 0, "battery_mv": 0,
     "temperature_cdeg": -4000, "mode": "SAFE", "fault_flags": 0,
     "origin": "SPACECRAFT"},
    {"sequence": 0xFFFF, "mission_time_ms": 0xFFFFFFFF, "battery_mv": 20000,
     "temperature_cdeg": 12500, "mode": "OBSERVATION", "fault_flags": 0xFFFF,
     "origin": "SIMULATED"},
    {"sequence": 1, "mission_time_ms": 1000, "battery_mv": 7400,
     "temperature_cdeg": 2150, "mode": "NOMINAL", "fault_flags": 0,
     "origin": "SIMULATED"},
]


@pytest.fixture(scope="module")
def c_output(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("c_cross_check")
    exe = tmp / "emit_packets.exe"
    build = subprocess.run(
        [GCC, "-std=c99", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
         f"-I{ROOT / 'flight_core' / 'include'}",
         str(ROOT / "flight_core" / "src" / "telemetry.c"),
         str(ROOT / "flight_core" / "tools" / "emit_packets.c"),
         "-o", str(exe)],
        capture_output=True, text=True)
    assert build.returncode == 0, build.stderr
    out = tmp / "packets.bin"
    run = subprocess.run([str(exe), str(out)], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    return out.read_bytes()


def test_c_output_has_exactly_four_packets(c_output):
    assert len(c_output) == PACKET_SIZE * len(EXPECTED)


def test_python_decodes_every_field_the_c_encoder_wrote(c_output):
    decoded = [decode_packet(c_output[i:i + PACKET_SIZE])
               for i in range(0, len(c_output), PACKET_SIZE)]
    assert decoded == EXPECTED


def test_corrupting_c_output_is_caught_by_python(c_output):
    bad = bytearray(c_output[:PACKET_SIZE])
    bad[8] ^= 0x01
    with pytest.raises(ValueError):
        decode_packet(bytes(bad))