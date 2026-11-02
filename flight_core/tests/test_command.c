#include <stdio.h>
#include <string.h>

#include "command.h"

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

static void healthy(hm_t *hm)
{
    hm_inputs_t in;
    in.battery_mv = 8000u;
    in.temperature_cdeg = 2000;
    in.sensors_valid = 1u;
    (void)hm_init(hm, 100u);
    (void)hm_update(hm, &in, 100u);
}

static void make(uint8_t *buf, uint16_t seq, uint8_t cmd)
{
    cmd_packet_t p;
    p.sequence = seq;
    p.command = cmd;
    (void)cmd_encode(&p, buf, CMD_PACKET_SIZE);
}

static void reseal(uint8_t *buf)
{
    uint16_t crc = tm_crc16(buf, CMD_PACKET_SIZE - 2u);
    buf[6] = (uint8_t)(crc & 0xFFu);
    buf[7] = (uint8_t)(crc >> 8);
}

static void test_encoding_layout_and_crc(void)
{
    uint8_t buf[CMD_PACKET_SIZE];
    make(buf, 0x0102u, CMD_ID_GOTO_NOMINAL);
    CHECK(buf[0] == 0xA5 && buf[1] == 0xC3);
    CHECK(buf[2] == 0x01);
    CHECK(buf[3] == 0x02 && buf[4] == 0x01);
    CHECK(buf[5] == 0x01);
    CHECK((uint16_t)(buf[6] | (buf[7] << 8)) == tm_crc16(buf, 6));
}

static void test_round_trip_of_every_command(void)
{
    uint8_t buf[CMD_PACKET_SIZE];
    cmd_packet_t in;
    cmd_packet_t out;
    uint8_t c;
    for (c = 0; c <= CMD_ID_MAX; c++) {
        in.sequence = (uint16_t)(1000u + c);
        in.command = c;
        CHECK(cmd_encode(&in, buf, sizeof buf) == CMD_OK);
        CHECK(cmd_decode(buf, sizeof buf, &out) == CMD_OK);
        CHECK(out.sequence == in.sequence && out.command == in.command);
    }
}

static void test_every_single_bit_error_is_rejected(void)
{
    uint8_t buf[CMD_PACKET_SIZE];
    uint8_t copy[CMD_PACKET_SIZE];
    cmd_packet_t out;
    size_t i;
    int bit;
    int accepted = 0;
    make(buf, 77u, CMD_ID_GOTO_NOMINAL);
    for (i = 0; i < CMD_PACKET_SIZE; i++) {
        for (bit = 0; bit < 8; bit++) {
            memcpy(copy, buf, sizeof copy);
            copy[i] ^= (uint8_t)(1u << bit);
            if (cmd_decode(copy, sizeof copy, &out) == CMD_OK) accepted++;
        }
    }
    CHECK(accepted == 0);
}

static void test_wrong_lengths_and_nulls(void)
{
    uint8_t buf[CMD_PACKET_SIZE + 1u];
    cmd_packet_t p;
    cmd_packet_t out;
    p.sequence = 1u;
    p.command = CMD_ID_GOTO_SAFE;
    make(buf, 1u, CMD_ID_GOTO_SAFE);
    buf[CMD_PACKET_SIZE] = 0u;
    CHECK(cmd_decode(buf, CMD_PACKET_SIZE - 1u, &out) == CMD_ERR_LENGTH);
    CHECK(cmd_decode(buf, CMD_PACKET_SIZE + 1u, &out) == CMD_ERR_LENGTH);
    CHECK(cmd_encode(&p, buf, CMD_PACKET_SIZE - 1u) == CMD_ERR_LENGTH);
    CHECK(cmd_decode(NULL, CMD_PACKET_SIZE, &out) == CMD_ERR_NULL);
    CHECK(cmd_decode(buf, CMD_PACKET_SIZE, NULL) == CMD_ERR_NULL);
    CHECK(cmd_encode(NULL, buf, CMD_PACKET_SIZE) == CMD_ERR_NULL);
    CHECK(cmd_encode(&p, NULL, CMD_PACKET_SIZE) == CMD_ERR_NULL);
}

static void test_bad_fields_with_a_valid_crc_are_still_rejected(void)
{
    uint8_t buf[CMD_PACKET_SIZE];
    cmd_packet_t out;

    make(buf, 5u, CMD_ID_GOTO_SAFE);
    buf[0] = 0x00; reseal(buf);
    CHECK(cmd_decode(buf, sizeof buf, &out) == CMD_ERR_SYNC);

    make(buf, 5u, CMD_ID_GOTO_SAFE);
    buf[2] = 9; reseal(buf);
    CHECK(cmd_decode(buf, sizeof buf, &out) == CMD_ERR_VERSION);

    make(buf, 5u, CMD_ID_GOTO_SAFE);
    buf[5] = 7; reseal(buf);
    CHECK(cmd_decode(buf, sizeof buf, &out) == CMD_ERR_RANGE);

    {
        cmd_packet_t bad;
        bad.sequence = 1u;
        bad.command = 7;
        CHECK(cmd_encode(&bad, buf, sizeof buf) == CMD_ERR_RANGE);
    }
}

static void test_sequence_window_edges(void)
{
    hm_t hm;
    cmd_rx_t rx;
    uint8_t buf[CMD_PACKET_SIZE];

    healthy(&hm);
    cmd_rx_init(&rx, 0u);

    make(buf, 32u, CMD_ID_GOTO_SAFE);   /* distance 32: the last accepted */
    CHECK(cmd_rx_process(&rx, &hm, buf, sizeof buf) == CMD_OK);
    make(buf, 65u, CMD_ID_GOTO_SAFE);   /* distance 33: too far */
    CHECK(cmd_rx_process(&rx, &hm, buf, sizeof buf) == CMD_ERR_SEQUENCE);
    make(buf, 64u, CMD_ID_GOTO_SAFE);   /* distance 32 again */
    CHECK(cmd_rx_process(&rx, &hm, buf, sizeof buf) == CMD_OK);
    make(buf, 64u, CMD_ID_GOTO_SAFE);   /* replay */
    CHECK(cmd_rx_process(&rx, &hm, buf, sizeof buf) == CMD_ERR_SEQUENCE);
    make(buf, 63u, CMD_ID_GOTO_SAFE);   /* old */
    CHECK(cmd_rx_process(&rx, &hm, buf, sizeof buf) == CMD_ERR_SEQUENCE);
}

static void test_sequence_wraps_around(void)
{
    hm_t hm;
    cmd_rx_t rx;
    uint8_t buf[CMD_PACKET_SIZE];

    healthy(&hm);
    cmd_rx_init(&rx, 65530u);
    make(buf, 2u, CMD_ID_GOTO_SAFE);    /* 8 ahead, across the 16-bit wrap */
    CHECK(cmd_rx_process(&rx, &hm, buf, sizeof buf) == CMD_OK);
    CHECK(rx.last_seq == 2u);
}

static void test_invalid_packets_do_not_consume_the_sequence(void)
{
    hm_t hm;
    cmd_rx_t rx;
    uint8_t buf[CMD_PACKET_SIZE];
    uint8_t good[CMD_PACKET_SIZE];

    healthy(&hm);
    cmd_rx_init(&rx, 0u);
    make(good, 1u, CMD_ID_GOTO_NOMINAL);

    memcpy(buf, good, sizeof buf);
    buf[5] ^= 0x01;                              /* corrupt: CRC no longer matches */
    CHECK(cmd_rx_process(&rx, &hm, buf, sizeof buf) == CMD_ERR_CRC);
    CHECK(rx.last_seq == 0u);
    CHECK(cmd_rx_process(&rx, &hm, good, sizeof good) == CMD_OK);
    CHECK(hm.mode == TM_MODE_NOMINAL);
}

static void test_monitor_refusal_consumes_the_sequence(void)
{
    hm_t hm;
    cmd_rx_t rx;
    uint8_t buf[CMD_PACKET_SIZE];

    healthy(&hm);                                /* starts in SAFE */
    cmd_rx_init(&rx, 0u);
    make(buf, 1u, CMD_ID_GOTO_OBSERVATION);      /* not allowed from SAFE */
    CHECK(cmd_rx_process(&rx, &hm, buf, sizeof buf) == CMD_ERR_REFUSED);
    CHECK(hm.mode == TM_MODE_SAFE);
    CHECK(rx.last_seq == 1u);
    CHECK(cmd_rx_process(&rx, &hm, buf, sizeof buf) == CMD_ERR_SEQUENCE);
}

static void test_counters(void)
{
    hm_t hm;
    cmd_rx_t rx;
    uint8_t buf[CMD_PACKET_SIZE];

    healthy(&hm);
    cmd_rx_init(&rx, 0u);
    make(buf, 1u, CMD_ID_GOTO_SAFE);
    (void)cmd_rx_process(&rx, &hm, buf, sizeof buf);          /* executed */
    (void)cmd_rx_process(&rx, &hm, buf, sizeof buf);          /* replay: invalid */
    make(buf, 2u, CMD_ID_GOTO_OBSERVATION);
    (void)cmd_rx_process(&rx, &hm, buf, sizeof buf);          /* refused */
    make(buf, 3u, CMD_ID_GOTO_SAFE);
    buf[6] ^= 0x01;
    (void)cmd_rx_process(&rx, &hm, buf, sizeof buf);          /* bad CRC: invalid */
    CHECK(rx.n_executed == 1u && rx.n_refused == 1u && rx.n_invalid == 2u);
}

static void test_safe_is_accepted_during_a_critical_fault_but_nominal_is_not(void)
{
    hm_t hm;
    cmd_rx_t rx;
    hm_inputs_t in;
    uint8_t buf[CMD_PACKET_SIZE];

    (void)hm_init(&hm, 100u);
    in.battery_mv = 6700u;                       /* below the critical threshold */
    in.temperature_cdeg = 2000;
    in.sensors_valid = 1u;
    (void)hm_update(&hm, &in, 100u);
    CHECK((hm.faults & HM_FAULT_BATT_CRITICAL) != 0u);

    cmd_rx_init(&rx, 0u);
    make(buf, 1u, CMD_ID_GOTO_NOMINAL);
    CHECK(cmd_rx_process(&rx, &hm, buf, sizeof buf) == CMD_ERR_REFUSED);
    make(buf, 2u, CMD_ID_GOTO_SAFE);
    CHECK(cmd_rx_process(&rx, &hm, buf, sizeof buf) == CMD_OK);
    CHECK(hm.mode == TM_MODE_SAFE);
}

static void test_null_arguments_and_status_names(void)
{
    hm_t hm;
    cmd_rx_t rx;
    uint8_t buf[CMD_PACKET_SIZE];

    healthy(&hm);
    cmd_rx_init(&rx, 0u);
    make(buf, 1u, CMD_ID_GOTO_SAFE);
    CHECK(cmd_rx_process(NULL, &hm, buf, sizeof buf) == CMD_ERR_NULL);
    CHECK(cmd_rx_process(&rx, NULL, buf, sizeof buf) == CMD_ERR_NULL);
    CHECK(strcmp(cmd_status_name(CMD_OK), "OK") == 0);
    CHECK(strcmp(cmd_status_name(CMD_ERR_REFUSED), "REFUSED") == 0);
    CHECK(strcmp(cmd_status_name((cmd_status_t)99), "UNKNOWN") == 0);
}

int main(void)
{
    test_encoding_layout_and_crc();
    test_round_trip_of_every_command();
    test_every_single_bit_error_is_rejected();
    test_wrong_lengths_and_nulls();
    test_bad_fields_with_a_valid_crc_are_still_rejected();
    test_sequence_window_edges();
    test_sequence_wraps_around();
    test_invalid_packets_do_not_consume_the_sequence();
    test_monitor_refusal_consumes_the_sequence();
    test_counters();
    test_safe_is_accepted_during_a_critical_fault_but_nominal_is_not();
    test_null_arguments_and_status_names();
    printf("%d checks, %d failed\n", g_checks, g_failed);
    return g_failed == 0 ? 0 : 1;
}