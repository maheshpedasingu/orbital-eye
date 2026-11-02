#ifndef COMMAND_H
#define COMMAND_H

#include <stddef.h>
#include <stdint.h>

#include "health.h"
#include "telemetry.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Project-chosen layout (not a standard). 8 bytes, little-endian on the wire:
   sync(2) version(1) sequence(2) command(1) crc16(2, over the first 6 bytes). */
#define CMD_SYNC_WORD 0xC3A5
#define CMD_VERSION 1
#define CMD_PACKET_SIZE 8u
#define CMD_SEQ_WINDOW 32u   /* accepted distance ahead of the last sequence: 1 to 32 */

typedef enum {
    CMD_ID_GOTO_SAFE = 0,
    CMD_ID_GOTO_NOMINAL = 1,
    CMD_ID_GOTO_OBSERVATION = 2
} cmd_id_t;
#define CMD_ID_MAX 2

typedef enum {
    CMD_OK = 0,
    CMD_ERR_NULL,
    CMD_ERR_LENGTH,
    CMD_ERR_SYNC,
    CMD_ERR_VERSION,
    CMD_ERR_CRC,
    CMD_ERR_RANGE,     /* unknown command id */
    CMD_ERR_SEQUENCE,  /* replay, too old, or too far ahead */
    CMD_ERR_REFUSED    /* valid packet, but the health monitor refused the command */
} cmd_status_t;

typedef struct {
    uint16_t sequence;
    uint8_t  command;  /* cmd_id_t */
} cmd_packet_t;

typedef struct {
    uint16_t last_seq;     /* last sequence number consumed */
    uint32_t n_executed;   /* commands accepted by the health monitor */
    uint32_t n_refused;    /* valid, in-window, but refused by the monitor */
    uint32_t n_invalid;    /* dropped: bad framing, CRC, range or sequence */
} cmd_rx_t;

/* Ground-side style encoder. Writes CMD_PACKET_SIZE bytes; the buffer is untouched on error. */
cmd_status_t cmd_encode(const cmd_packet_t *pkt, uint8_t *buf, size_t buf_len);

/* Validates framing, CRC and command range. Does NOT check the sequence number.
   *out is untouched on error. */
cmd_status_t cmd_decode(const uint8_t *buf, size_t buf_len, cmd_packet_t *out);

void cmd_rx_init(cmd_rx_t *rx, uint16_t last_seq);

/* Full receive path: decode, check the sequence window, then run the command on the monitor. */
cmd_status_t cmd_rx_process(cmd_rx_t *rx, hm_t *hm, const uint8_t *buf, size_t buf_len);

const char *cmd_status_name(cmd_status_t st);

#ifdef __cplusplus
}
#endif

#endif /* COMMAND_H */