#include <stdio.h>
#include <string.h>

#include "telemetry.h"

static int g_checks = 0;
static int g_failed = 0;

#define CHECK(cond)                                                    \
    do {                                                               \
        g_checks++;                                                    \
        if (!(cond)) {                                                 \
            g_failed++;                                                \
            printf("FAIL line %d: %s\n", __LINE__, #cond);             \
        }                                                              \
    } while (0)

static tm_packet_t sample(void)
{
    tm_packet_t p;
    p.sequence = 0x0102u;
    p.mission_time_ms = 0x0A0B0C0Du;
    p.battery_mv = 8000u;
    p.temperature_cdeg = -250;
    p.mode = TM_MODE_NOMINAL;
    p.fault_flags = 0x0003u;
    p.origin = TM_ORIGIN_SIMULATED;
    return p;
}

static void test_crc_matches_published_check_value(void)
{
    const uint8_t msg[] = { '1', '2', '3', '4', '5', '6', '7', '8', '9' };
    CHECK(tm_crc16(msg, sizeof msg) == 0x29B1);
}

static void test_encoding_matches_hand_computed_bytes(void)
{
    /* Worked out by hand from the layout table (little-endian). */
    static const uint8_t expected[17] = {
        0x90, 0xEB, 0x01, 0x02, 0x01, 0x0D, 0x0C, 0x0B, 0x0A,
        0x40, 0x1F, 0x06, 0xFF, 0x01, 0x03, 0x00, 0x01
    };
    uint8_t buf[TM_PACKET_SIZE];
    tm_packet_t p = sample();
    CHECK(tm_encode(&p, buf, sizeof buf) == TM_OK);
    CHECK(memcmp(buf, expected, 17) == 0);
    CHECK((buf[17] | (buf[18] << 8)) == tm_crc16(buf, 17));
}

static void test_round_trip_including_negative_temperature(void)
{
    uint8_t buf[TM_PACKET_SIZE];
    tm_packet_t in = sample();
    tm_packet_t out;
    memset(&out, 0, sizeof out);
    CHECK(tm_encode(&in, buf, sizeof buf) == TM_OK);
    CHECK(tm_decode(buf, sizeof buf, &out) == TM_OK);
    CHECK(out.sequence == in.sequence);
    CHECK(out.mission_time_ms == in.mission_time_ms);
    CHECK(out.battery_mv == in.battery_mv);
    CHECK(out.temperature_cdeg == -250);
    CHECK(out.mode == in.mode);
    CHECK(out.fault_flags == in.fault_flags);
    CHECK(out.origin == in.origin);
}

static void test_range_limits_round_trip(void)
{
    uint8_t buf[TM_PACKET_SIZE];
    tm_packet_t in = sample();
    tm_packet_t out;
    in.temperature_cdeg = TM_TEMP_MIN_CDEG;
    in.battery_mv = TM_BATTERY_MAX_MV;
    in.mission_time_ms = 0xFFFFFFFFu;
    CHECK(tm_encode(&in, buf, sizeof buf) == TM_OK);
    CHECK(tm_decode(buf, sizeof buf, &out) == TM_OK);
    CHECK(out.temperature_cdeg == TM_TEMP_MIN_CDEG);
    CHECK(out.mission_time_ms == 0xFFFFFFFFu);
    in.temperature_cdeg = TM_TEMP_MAX_CDEG;
    CHECK(tm_encode(&in, buf, sizeof buf) == TM_OK);
    CHECK(tm_decode(buf, sizeof buf, &out) == TM_OK);
    CHECK(out.temperature_cdeg == TM_TEMP_MAX_CDEG);
}

static void test_every_single_bit_error_is_detected(void)
{
    uint8_t buf[TM_PACKET_SIZE];
    uint8_t copy[TM_PACKET_SIZE];
    tm_packet_t p = sample();
    tm_packet_t out;
    size_t i;
    int bit;
    int undetected = 0;
    CHECK(tm_encode(&p, buf, sizeof buf) == TM_OK);
    for (i = 0; i < TM_PACKET_SIZE; i++) {
        for (bit = 0; bit < 8; bit++) {
            memcpy(copy, buf, sizeof copy);
            copy[i] ^= (uint8_t)(1u << bit);
            if (tm_decode(copy, sizeof copy, &out) == TM_OK) undetected++;
        }
    }
    CHECK(undetected == 0);
}

static void test_wrong_lengths_are_rejected(void)
{
    uint8_t buf[TM_PACKET_SIZE];
    uint8_t big[TM_PACKET_SIZE + 1u];
    tm_packet_t p = sample();
    tm_packet_t out;
    CHECK(tm_encode(&p, buf, sizeof buf) == TM_OK);
    memcpy(big, buf, sizeof buf);
    big[TM_PACKET_SIZE] = 0;
    CHECK(tm_encode(&p, buf, TM_PACKET_SIZE - 1u) == TM_ERR_BUFFER_SIZE);
    CHECK(tm_decode(buf, TM_PACKET_SIZE - 1u, &out) == TM_ERR_BUFFER_SIZE);
    CHECK(tm_decode(big, sizeof big, &out) == TM_ERR_BUFFER_SIZE);
}

static void test_out_of_range_fields_are_rejected(void)
{
    uint8_t buf[TM_PACKET_SIZE];
    tm_packet_t p;

    p = sample(); p.battery_mv = TM_BATTERY_MAX_MV + 1;
    CHECK(tm_encode(&p, buf, sizeof buf) == TM_ERR_RANGE);
    p = sample(); p.temperature_cdeg = TM_TEMP_MIN_CDEG - 1;
    CHECK(tm_encode(&p, buf, sizeof buf) == TM_ERR_RANGE);
    p = sample(); p.temperature_cdeg = TM_TEMP_MAX_CDEG + 1;
    CHECK(tm_encode(&p, buf, sizeof buf) == TM_ERR_RANGE);
    p = sample(); p.mode = TM_MODE_MAX + 1;
    CHECK(tm_encode(&p, buf, sizeof buf) == TM_ERR_RANGE);
    p = sample(); p.origin = TM_ORIGIN_INVALID;
    CHECK(tm_encode(&p, buf, sizeof buf) == TM_ERR_RANGE);
    p = sample(); p.origin = 3;
    CHECK(tm_encode(&p, buf, sizeof buf) == TM_ERR_RANGE);
}

static void test_valid_crc_with_bad_range_is_still_rejected(void)
{
    uint8_t buf[TM_PACKET_SIZE];
    tm_packet_t p = sample();
    tm_packet_t out;
    uint16_t crc;
    out.sequence = 0xFFFFu;
    CHECK(tm_encode(&p, buf, sizeof buf) == TM_OK);
    buf[13] = 9; /* invalid mode, then re-seal with a correct CRC */
    crc = tm_crc16(buf, 17);
    buf[17] = (uint8_t)(crc & 0xFFu);
    buf[18] = (uint8_t)(crc >> 8);
    CHECK(tm_decode(buf, sizeof buf, &out) == TM_ERR_RANGE);
    CHECK(out.sequence == 0xFFFFu); /* output untouched on error */
}

static void test_null_pointers_are_rejected(void)
{
    uint8_t buf[TM_PACKET_SIZE];
    tm_packet_t p = sample();
    tm_packet_t out;
    CHECK(tm_encode(&p, buf, sizeof buf) == TM_OK);
    CHECK(tm_encode(NULL, buf, sizeof buf) == TM_ERR_NULL);
    CHECK(tm_encode(&p, NULL, sizeof buf) == TM_ERR_NULL);
    CHECK(tm_decode(NULL, sizeof buf, &out) == TM_ERR_NULL);
    CHECK(tm_decode(buf, sizeof buf, NULL) == TM_ERR_NULL);
    CHECK(tm_validate(NULL) == TM_ERR_NULL);
}

int main(void)
{
    test_crc_matches_published_check_value();
    test_encoding_matches_hand_computed_bytes();
    test_round_trip_including_negative_temperature();
    test_range_limits_round_trip();
    test_every_single_bit_error_is_detected();
    test_wrong_lengths_are_rejected();
    test_out_of_range_fields_are_rejected();
    test_valid_crc_with_bad_range_is_still_rejected();
    test_null_pointers_are_rejected();
    printf("%d checks, %d failed\n", g_checks, g_failed);
    return g_failed == 0 ? 0 : 1;
}