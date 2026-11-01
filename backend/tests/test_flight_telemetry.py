import pytest

from app.flight_telemetry import crc16_ccitt_false, decode_packet

# The same 17 bytes the C test hand-computed from the layout table.
PREFIX = bytes([0x90, 0xEB, 0x01, 0x02, 0x01, 0x0D, 0x0C, 0x0B, 0x0A,
                0x40, 0x1F, 0x06, 0xFF, 0x01, 0x03, 0x00, 0x01])


def sealed(prefix: bytes = PREFIX) -> bytes:
    return prefix + crc16_ccitt_false(prefix).to_bytes(2, "little")


def test_check_value_matches_published_standard():
    assert crc16_ccitt_false(b"123456789") == 0x29B1


def test_decodes_the_same_fields_the_c_test_expects():
    p = decode_packet(sealed())
    assert p == {
        "sequence": 0x0102,
        "mission_time_ms": 0x0A0B0C0D,
        "battery_mv": 8000,
        "temperature_cdeg": -250,
        "mode": "NOMINAL",
        "fault_flags": 0x0003,
        "origin": "SIMULATED",
    }


def test_single_bit_flips_are_all_rejected():
    good = sealed()
    for i in range(len(good)):
        for bit in range(8):
            bad = bytearray(good)
            bad[i] ^= 1 << bit
            with pytest.raises(ValueError):
                decode_packet(bytes(bad))


def test_wrong_length_is_rejected():
    with pytest.raises(ValueError):
        decode_packet(sealed()[:-1])


def test_bad_sync_is_rejected():
    prefix = bytearray(PREFIX)
    prefix[0] = 0x00
    with pytest.raises(ValueError, match="sync"):
        decode_packet(sealed(bytes(prefix)))


def test_invalid_mode_with_valid_crc_is_still_rejected():
    prefix = bytearray(PREFIX)
    prefix[13] = 9
    with pytest.raises(ValueError, match="mode"):
        decode_packet(sealed(bytes(prefix)))


def test_temperature_limits_are_inclusive():
    prefix = bytearray(PREFIX)
    prefix[11:13] = (-4000 & 0xFFFF).to_bytes(2, "little")
    assert decode_packet(sealed(bytes(prefix)))["temperature_cdeg"] == -4000
    prefix[11:13] = (-4001 & 0xFFFF).to_bytes(2, "little")
    with pytest.raises(ValueError, match="temperature"):
        decode_packet(sealed(bytes(prefix)))