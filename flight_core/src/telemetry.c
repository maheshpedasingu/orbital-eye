#include "telemetry.h"

static void put_u16(uint8_t *p, uint16_t v)
{
    p[0] = (uint8_t)(v & 0xFFu);
    p[1] = (uint8_t)((v >> 8) & 0xFFu);
}

static void put_u32(uint8_t *p, uint32_t v)
{
    p[0] = (uint8_t)(v & 0xFFu);
    p[1] = (uint8_t)((v >> 8) & 0xFFu);
    p[2] = (uint8_t)((v >> 16) & 0xFFu);
    p[3] = (uint8_t)((v >> 24) & 0xFFu);
}

static uint16_t get_u16(const uint8_t *p)
{
    return (uint16_t)((uint16_t)p[0] | (uint16_t)((uint16_t)p[1] << 8));
}

static uint32_t get_u32(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

uint16_t tm_crc16(const uint8_t *data, size_t len)
{
    uint16_t crc = 0xFFFFu;
    size_t i;
    int b;
    for (i = 0; i < len; i++) {
        crc ^= (uint16_t)((uint16_t)data[i] << 8);
        for (b = 0; b < 8; b++) {
            if (crc & 0x8000u) {
                crc = (uint16_t)((crc << 1) ^ 0x1021u);
            } else {
                crc = (uint16_t)(crc << 1);
            }
        }
    }
    return crc;
}

tm_status_t tm_validate(const tm_packet_t *pkt)
{
    if (pkt == NULL) return TM_ERR_NULL;
    if (pkt->battery_mv > TM_BATTERY_MAX_MV) return TM_ERR_RANGE;
    if (pkt->temperature_cdeg < TM_TEMP_MIN_CDEG ||
        pkt->temperature_cdeg > TM_TEMP_MAX_CDEG) return TM_ERR_RANGE;
    if (pkt->mode > TM_MODE_MAX) return TM_ERR_RANGE;
    if (pkt->origin != TM_ORIGIN_SIMULATED &&
        pkt->origin != TM_ORIGIN_SPACECRAFT) return TM_ERR_RANGE;
    return TM_OK;
}

tm_status_t tm_encode(const tm_packet_t *pkt, uint8_t *buf, size_t buf_len)
{
    if (pkt == NULL || buf == NULL) return TM_ERR_NULL;
    if (buf_len < TM_PACKET_SIZE) return TM_ERR_BUFFER_SIZE;
    if (tm_validate(pkt) != TM_OK) return TM_ERR_RANGE;

    put_u16(buf + 0, TM_SYNC_WORD);
    buf[2] = (uint8_t)TM_VERSION;
    put_u16(buf + 3, pkt->sequence);
    put_u32(buf + 5, pkt->mission_time_ms);
    put_u16(buf + 9, pkt->battery_mv);
    put_u16(buf + 11, (uint16_t)pkt->temperature_cdeg);
    buf[13] = pkt->mode;
    put_u16(buf + 14, pkt->fault_flags);
    buf[16] = pkt->origin;
    put_u16(buf + 17, tm_crc16(buf, TM_PACKET_SIZE - 2u));
    return TM_OK;
}

tm_status_t tm_decode(const uint8_t *buf, size_t buf_len, tm_packet_t *out)
{
    tm_packet_t tmp;
    uint16_t temp_raw;

    if (buf == NULL || out == NULL) return TM_ERR_NULL;
    if (buf_len != TM_PACKET_SIZE) return TM_ERR_BUFFER_SIZE;
    if (get_u16(buf) != TM_SYNC_WORD) return TM_ERR_SYNC;
    if (buf[2] != TM_VERSION) return TM_ERR_VERSION;
    if (get_u16(buf + 17) != tm_crc16(buf, TM_PACKET_SIZE - 2u)) return TM_ERR_CRC;

    temp_raw = get_u16(buf + 11);
    tmp.sequence = get_u16(buf + 3);
    tmp.mission_time_ms = get_u32(buf + 5);
    tmp.battery_mv = get_u16(buf + 9);
    tmp.temperature_cdeg =
        (int16_t)(temp_raw >= 0x8000 ? (int32_t)temp_raw - 65536 : (int32_t)temp_raw);
    tmp.mode = buf[13];
    tmp.fault_flags = get_u16(buf + 14);
    tmp.origin = buf[16];

    if (tm_validate(&tmp) != TM_OK) return TM_ERR_RANGE;
    *out = tmp;
    return TM_OK;
}