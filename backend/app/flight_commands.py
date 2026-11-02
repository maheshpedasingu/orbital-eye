"""Independent Python encoder for the 8-byte command packet (see flight_core/include/command.h).

Written from the layout table, not from the C code. NOT authenticated: anyone with this
file can build packets the receiver accepts. See docs for the security limits.
"""
import struct

from app.flight_telemetry import crc16_ccitt_false

SYNC_WORD = 0xC3A5
VERSION = 1
PACKET_SIZE = 8
COMMANDS = {"GOTO_SAFE": 0, "GOTO_NOMINAL": 1, "GOTO_OBSERVATION": 2}

_BODY_FORMAT = "<HBHB"   # sync, version, sequence, command (CRC appended afterwards)
assert struct.calcsize(_BODY_FORMAT) == PACKET_SIZE - 2


def encode_command(sequence: int, command) -> bytes:
    """Build one command packet. `command` is a name or a raw id (0 to 255).

    Raw ids outside 0 to 2 are allowed on purpose, to build invalid packets for tests.
    """
    if not 0 <= sequence <= 0xFFFF:
        raise ValueError("sequence must fit in 16 bits")
    if isinstance(command, str):
        if command not in COMMANDS:
            raise ValueError(f"unknown command {command!r}")
        command = COMMANDS[command]
    if not 0 <= command <= 255:
        raise ValueError("command id must fit in 8 bits")
    body = struct.pack(_BODY_FORMAT, SYNC_WORD, VERSION, sequence, command)
    return body + crc16_ccitt_false(body).to_bytes(2, "little")