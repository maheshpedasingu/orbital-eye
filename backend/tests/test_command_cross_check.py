import shutil
import subprocess
from pathlib import Path

import pytest

from app.flight_commands import PACKET_SIZE, encode_command
from app.flight_telemetry import crc16_ccitt_false

ROOT = Path(__file__).resolve().parents[2]
FLIGHT = ROOT / "flight_core"
GCC = shutil.which("gcc")


def flipped(data: bytes, index: int, bit: int) -> bytes:
    b = bytearray(data)
    b[index] ^= 1 << bit
    return bytes(b)


# (packet, expected verdict, expected mode afterwards) written by hand from the receiver rules.
# The monitor starts healthy, in SAFE, and the receiver's last sequence is 0.
CASES = [
    (encode_command(1, "GOTO_NOMINAL"), "OK", "NOMINAL"),
    (encode_command(2, "GOTO_OBSERVATION"), "OK", "OBSERVATION"),
    (encode_command(2, "GOTO_SAFE"), "SEQUENCE", "OBSERVATION"),      # same number, other command
    (flipped(encode_command(3, "GOTO_SAFE"), 5, 0), "CRC", "OBSERVATION"),
    (encode_command(4, "GOTO_SAFE"), "OK", "SAFE"),                    # 4 is 2 ahead of 2: in window
    (encode_command(5, "GOTO_OBSERVATION"), "REFUSED", "SAFE"),        # not allowed from SAFE
    (encode_command(5, "GOTO_NOMINAL"), "SEQUENCE", "SAFE"),           # 5 was consumed by the refusal
    (encode_command(100, "GOTO_NOMINAL"), "SEQUENCE", "SAFE"),         # 95 ahead: outside the window
    (encode_command(6, 7), "RANGE", "SAFE"),                           # unknown id, valid CRC
    (encode_command(6, "GOTO_NOMINAL"), "OK", "NOMINAL"),              # 6 was NOT consumed by the invalid one
]


def test_python_encoder_matches_the_documented_layout():
    p = encode_command(0x0102, "GOTO_NOMINAL")
    assert len(p) == PACKET_SIZE == 8
    assert p[:6] == bytes([0xA5, 0xC3, 0x01, 0x02, 0x01, 0x01])
    assert crc16_ccitt_false(p[:6]) == int.from_bytes(p[6:], "little")


def test_encoder_rejects_impossible_arguments():
    for args in ((-1, "GOTO_SAFE"), (70000, "GOTO_SAFE"), (1, "SELF_DESTRUCT"), (1, 256)):
        with pytest.raises(ValueError):
            encode_command(*args)


@pytest.fixture(scope="module")
def verdicts(tmp_path_factory):
    if GCC is None:
        pytest.skip("gcc not found on PATH")
    tmp = tmp_path_factory.mktemp("command_cross_check")
    exe = tmp / "run_commands.exe"
    build = subprocess.run(
        [GCC, "-std=c99", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
         f"-I{FLIGHT / 'include'}",
         str(FLIGHT / "src" / "telemetry.c"),
         str(FLIGHT / "src" / "health.c"),
         str(FLIGHT / "src" / "command.c"),
         str(FLIGHT / "tools" / "run_commands.c"),
         "-o", str(exe)],
        capture_output=True, text=True)
    assert build.returncode == 0, build.stderr
    packets = tmp / "packets.bin"
    packets.write_bytes(b"".join(p for p, _, _ in CASES))
    run = subprocess.run([str(exe), str(packets)], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    return [line.split() for line in run.stdout.strip().splitlines()]


def test_the_real_receiver_gives_the_hand_written_verdict_for_every_packet(verdicts):
    assert len(verdicts) == len(CASES)
    for i, (_, status, mode) in enumerate(CASES):
        assert verdicts[i] == [str(i), status, mode], f"packet {i}"