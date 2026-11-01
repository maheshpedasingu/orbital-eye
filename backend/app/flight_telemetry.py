"""Independent Python decoder for the 19-byte telemetry packet (see flight_core).

Written from the layout table, not from the C code, so the two can cross-check.
Labels: packets are SIMULATED or SPACECRAFT origin, as carried in the packet.
"""
import struct

SYNC_WORD = 0xEB90
VERSION = 1
PACKET_SIZE = 19
MODES = {0: "SAFE", 1: "NOMINAL", 2: "OBSERVATION"}
ORIGINS = {1: "SIMULATED", 2: "SPACECRAFT"}
BATTERY_MAX_MV = 20000
TEMP_MIN_CDEG = -4000
TEMP_MAX_CDEG = 12500

# sync, version, sequence, mission_time_ms, battery_mv, temp_cdeg, mode, faults, origin, crc
_FORMAT = "<HBHIHhBHBH"
assert struct.calcsize(_FORMAT) == PACKET_SIZE


def crc16_ccitt_false(data: bytes) -> int:
    """CRC-16/CCITT-FALSE: poly 0x1021, init 0xFFFF, no reflection, no final XOR."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return crc


def decode_packet(buf: bytes) -> dict:
    """Decode and validate one packet. Raises ValueError with the reason."""
    if len(buf) != PACKET_SIZE:
        raise ValueError(f"wrong length {len(buf)}, expected {PACKET_SIZE}")
    sync, version, seq, time_ms, battery, temp, mode, faults, origin, crc = \
        struct.unpack(_FORMAT, buf)
    if sync != SYNC_WORD:
        raise ValueError("bad sync word")
    if version != VERSION:
        raise ValueError("bad version")
    if crc != crc16_ccitt_false(buf[:PACKET_SIZE - 2]):
        raise ValueError("CRC mismatch")
    if battery > BATTERY_MAX_MV:
        raise ValueError("battery out of range")
    if not TEMP_MIN_CDEG <= temp <= TEMP_MAX_CDEG:
        raise ValueError("temperature out of range")
    if mode not in MODES:
        raise ValueError("mode out of range")
    if origin not in ORIGINS:
        raise ValueError("origin out of range")
    return {
        "sequence": seq,
        "mission_time_ms": time_ms,
        "battery_mv": battery,
        "temperature_cdeg": temp,
        "mode": MODES[mode],
        "fault_flags": faults,
        "origin": ORIGINS[origin],
    }