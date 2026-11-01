#ifndef TELEMETRY_H
#define TELEMETRY_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Project-chosen constants (not a standard). Little-endian on the wire. */
#define TM_SYNC_WORD 0xEB90
#define TM_VERSION 1
#define TM_PACKET_SIZE 19u

/* Allowed ranges (illustrative) */
#define TM_BATTERY_MAX_MV 20000    /* millivolts */
#define TM_TEMP_MIN_CDEG (-4000)   /* 0.01 degC, i.e. -40.00 C */
#define TM_TEMP_MAX_CDEG 12500     /* +125.00 C */
#define TM_MODE_MAX 2

typedef enum { TM_MODE_SAFE = 0, TM_MODE_NOMINAL = 1, TM_MODE_OBSERVATION = 2 } tm_mode_t;
typedef enum { TM_ORIGIN_INVALID = 0, TM_ORIGIN_SIMULATED = 1, TM_ORIGIN_SPACECRAFT = 2 } tm_origin_t;

typedef enum {
    TM_OK = 0,
    TM_ERR_NULL,
    TM_ERR_BUFFER_SIZE,
    TM_ERR_SYNC,
    TM_ERR_VERSION,
    TM_ERR_CRC,
    TM_ERR_RANGE
} tm_status_t;

typedef struct {
    uint16_t sequence;         /* counter */
    uint32_t mission_time_ms;  /* milliseconds, wraps at 2^32 */
    uint16_t battery_mv;       /* millivolts */
    int16_t  temperature_cdeg; /* hundredths of a degree Celsius */
    uint8_t  mode;             /* tm_mode_t */
    uint16_t fault_flags;      /* bitfield, meaning defined elsewhere */
    uint8_t  origin;           /* tm_origin_t: SIMULATED or SPACECRAFT */
} tm_packet_t;

/* CRC-16/CCITT-FALSE: poly 0x1021, init 0xFFFF, no reflection, no final XOR. */
uint16_t tm_crc16(const uint8_t *data, size_t len);

/* TM_OK if all fields are within their allowed ranges, else TM_ERR_RANGE. */
tm_status_t tm_validate(const tm_packet_t *pkt);

/* Writes exactly TM_PACKET_SIZE bytes. The buffer is untouched on error. */
tm_status_t tm_encode(const tm_packet_t *pkt, uint8_t *buf, size_t buf_len);

/* buf_len must equal TM_PACKET_SIZE. *out is untouched on error. */
tm_status_t tm_decode(const uint8_t *buf, size_t buf_len, tm_packet_t *out);

#ifdef __cplusplus
}
#endif

#endif /* TELEMETRY_H */