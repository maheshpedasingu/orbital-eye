#include <stdio.h>

#include "health.h"

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

static hm_inputs_t reading(uint16_t batt_mv, int16_t temp_cdeg, uint8_t valid)
{
    hm_inputs_t in;
    in.battery_mv = batt_mv;
    in.temperature_cdeg = temp_cdeg;
    in.sensors_valid = valid;
    return in;
}

static void up(hm_t *hm, uint16_t batt_mv, int16_t temp_cdeg, uint32_t now_ms)
{
    hm_inputs_t in = reading(batt_mv, temp_cdeg, 1u);
    (void)hm_update(hm, &in, now_ms);
}

static void test_starts_in_safe_and_stays_latched(void)
{
    hm_t hm;
    CHECK(hm_init(&hm, 0u) == HM_OK);
    CHECK(hm.mode == TM_MODE_SAFE && hm.faults == 0u && hm.sequence == 0u);
    up(&hm, 8000u, 2000, 100u);
    CHECK(hm.mode == TM_MODE_SAFE); /* healthy readings do not leave SAFE */
    CHECK(hm.faults == 0u);
}

static void test_command_paths(void)
{
    hm_t hm;
    hm_init(&hm, 0u);
    CHECK(hm_command(&hm, HM_CMD_GOTO_OBSERVATION) == HM_ERR_REJECTED); /* not from SAFE */
    CHECK(hm.mode == TM_MODE_SAFE);
    up(&hm, 8000u, 2000, 100u);
    CHECK(hm_command(&hm, HM_CMD_GOTO_NOMINAL) == HM_OK);
    CHECK(hm.mode == TM_MODE_NOMINAL);
    CHECK(hm_command(&hm, HM_CMD_GOTO_OBSERVATION) == HM_OK);
    CHECK(hm.mode == TM_MODE_OBSERVATION);
    CHECK(hm_command(&hm, HM_CMD_GOTO_SAFE) == HM_OK);
    CHECK(hm.mode == TM_MODE_SAFE);
    CHECK(hm_command(&hm, (hm_cmd_t)99) == HM_ERR_INVALID_CMD);
}

static void test_low_battery_demotes_observation(void)
{
    hm_t hm;
    hm_init(&hm, 0u);
    up(&hm, 8000u, 2000, 100u);
    hm_command(&hm, HM_CMD_GOTO_NOMINAL);
    hm_command(&hm, HM_CMD_GOTO_OBSERVATION);
    up(&hm, 6900u, 2000, 200u); /* below 7200 but above 6800 */
    CHECK((hm.faults & HM_FAULT_BATT_LOW) != 0u);
    CHECK((hm.faults & HM_FAULT_BATT_CRITICAL) == 0u);
    CHECK(hm.mode == TM_MODE_NOMINAL); /* demoted, not SAFE */
    CHECK(hm_command(&hm, HM_CMD_GOTO_OBSERVATION) == HM_ERR_REJECTED);
    up(&hm, 7400u, 2000, 300u);
    CHECK(hm.faults == 0u);
    CHECK(hm_command(&hm, HM_CMD_GOTO_OBSERVATION) == HM_OK);
}

static void test_critical_battery_forces_safe_and_needs_a_command(void)
{
    hm_t hm;
    hm_init(&hm, 0u);
    up(&hm, 8000u, 2000, 100u);
    hm_command(&hm, HM_CMD_GOTO_NOMINAL);
    hm_command(&hm, HM_CMD_GOTO_OBSERVATION);
    up(&hm, 6700u, 2000, 200u);
    CHECK((hm.faults & HM_FAULT_BATT_CRITICAL) != 0u);
    CHECK((hm.faults & HM_FAULT_BATT_LOW) != 0u);
    CHECK(hm.mode == TM_MODE_SAFE);
    CHECK(hm_command(&hm, HM_CMD_GOTO_NOMINAL) == HM_ERR_REJECTED);
    up(&hm, 7000u, 2000, 300u);
    CHECK((hm.faults & HM_FAULT_BATT_CRITICAL) == 0u);
    CHECK((hm.faults & HM_FAULT_BATT_LOW) != 0u);
    CHECK(hm.mode == TM_MODE_SAFE); /* recovery does not leave SAFE by itself */
    CHECK(hm_command(&hm, HM_CMD_GOTO_NOMINAL) == HM_OK);
    CHECK(hm_command(&hm, HM_CMD_GOTO_OBSERVATION) == HM_ERR_REJECTED); /* LOW still set */
}

static void test_battery_hysteresis(void)
{
    hm_t hm;
    hm_init(&hm, 0u);
    up(&hm, 8000u, 2000, 10u);
    CHECK(hm.faults == 0u);
    up(&hm, 7199u, 2000, 20u);
    CHECK((hm.faults & HM_FAULT_BATT_LOW) != 0u);
    up(&hm, 7399u, 2000, 30u);
    CHECK((hm.faults & HM_FAULT_BATT_LOW) != 0u); /* still latched inside the band */
    up(&hm, 7400u, 2000, 40u);
    CHECK((hm.faults & HM_FAULT_BATT_LOW) == 0u);
    up(&hm, 6799u, 2000, 50u);
    CHECK((hm.faults & HM_FAULT_BATT_CRITICAL) != 0u);
    up(&hm, 6999u, 2000, 60u);
    CHECK((hm.faults & HM_FAULT_BATT_CRITICAL) != 0u);
    up(&hm, 7000u, 2000, 70u);
    CHECK((hm.faults & HM_FAULT_BATT_CRITICAL) == 0u);
}

static void test_temperature_thresholds_and_hysteresis(void)
{
    hm_t hm;
    hm_init(&hm, 0u);
    up(&hm, 8000u, 2000, 10u);
    hm_command(&hm, HM_CMD_GOTO_NOMINAL);
    up(&hm, 8000u, 6000, 20u);
    CHECK((hm.faults & HM_FAULT_TEMP_HIGH) == 0u); /* the limit itself is allowed */
    CHECK(hm.mode == TM_MODE_NOMINAL);
    up(&hm, 8000u, 6001, 30u);
    CHECK((hm.faults & HM_FAULT_TEMP_HIGH) != 0u);
    CHECK(hm.mode == TM_MODE_SAFE);
    up(&hm, 8000u, 5501, 40u);
    CHECK((hm.faults & HM_FAULT_TEMP_HIGH) != 0u);
    up(&hm, 8000u, 5500, 50u);
    CHECK((hm.faults & HM_FAULT_TEMP_HIGH) == 0u);

    hm_command(&hm, HM_CMD_GOTO_NOMINAL);
    up(&hm, 8000u, -1000, 60u);
    CHECK((hm.faults & HM_FAULT_TEMP_LOW) == 0u);
    up(&hm, 8000u, -1001, 70u);
    CHECK((hm.faults & HM_FAULT_TEMP_LOW) != 0u);
    CHECK(hm.mode == TM_MODE_NOMINAL); /* cold only blocks OBSERVATION */
    CHECK(hm_command(&hm, HM_CMD_GOTO_OBSERVATION) == HM_ERR_REJECTED);
    up(&hm, 8000u, -501, 80u);
    CHECK((hm.faults & HM_FAULT_TEMP_LOW) != 0u);
    up(&hm, 8000u, -500, 90u);
    CHECK((hm.faults & HM_FAULT_TEMP_LOW) == 0u);
}

static void test_invalid_and_out_of_range_sensors_are_faults(void)
{
    hm_t hm;
    hm_inputs_t bad = reading(1234u, 100, 0u);
    hm_init(&hm, 0u);
    up(&hm, 8000u, 2000, 10u);
    hm_command(&hm, HM_CMD_GOTO_NOMINAL);

    hm_update(&hm, &bad, 20u);
    CHECK((hm.faults & HM_FAULT_SENSOR_INVALID) != 0u);
    CHECK(hm.mode == TM_MODE_SAFE);
    CHECK(hm.battery_mv == 8000u); /* the bad reading was not stored */

    up(&hm, 8000u, 2000, 30u);
    CHECK((hm.faults & HM_FAULT_SENSOR_INVALID) == 0u);
    CHECK(hm.mode == TM_MODE_SAFE); /* still latched */

    up(&hm, 25000u, 2000, 40u); /* above the telemetry range */
    CHECK((hm.faults & HM_FAULT_SENSOR_INVALID) != 0u);
    CHECK(hm.battery_mv == 8000u);
    up(&hm, 8000u, 2000, 50u);
    up(&hm, 8000u, 20000, 60u); /* above the telemetry range */
    CHECK((hm.faults & HM_FAULT_SENSOR_INVALID) != 0u);
}

static void test_watchdog_timeout_and_recovery(void)
{
    hm_t hm;
    hm_init(&hm, 0u);
    hm_command(&hm, HM_CMD_GOTO_NOMINAL);
    up(&hm, 8000u, 2000, 5000u);
    CHECK((hm.faults & HM_FAULT_WATCHDOG) == 0u); /* exactly at the limit */
    CHECK(hm.mode == TM_MODE_NOMINAL);
    up(&hm, 8000u, 2000, 5001u);
    CHECK((hm.faults & HM_FAULT_WATCHDOG) != 0u);
    CHECK(hm.mode == TM_MODE_SAFE);
    hm_kick(&hm, 5200u);
    up(&hm, 8000u, 2000, 5300u);
    CHECK(hm.faults == 0u);
    CHECK(hm.mode == TM_MODE_SAFE); /* stays SAFE until commanded */
}

static void test_watchdog_survives_counter_wrap(void)
{
    hm_t hm;
    hm_init(&hm, 0xFFFFFF00u);
    up(&hm, 8000u, 2000, 0x000000FFu);   /* 511 ms later, across the wrap */
    CHECK((hm.faults & HM_FAULT_WATCHDOG) == 0u);
    up(&hm, 8000u, 2000, 0x00001500u);   /* 5632 ms later */
    CHECK((hm.faults & HM_FAULT_WATCHDOG) != 0u);
}

static void test_packet_carries_state_and_round_trips(void)
{
    hm_t hm;
    tm_packet_t p1;
    tm_packet_t p2;
    tm_packet_t back;
    uint8_t buf[TM_PACKET_SIZE];

    hm_init(&hm, 0u);
    up(&hm, 7100u, 2150, 100u);
    hm_command(&hm, HM_CMD_GOTO_NOMINAL);
    CHECK(hm_make_packet(&hm, 100u, TM_ORIGIN_SIMULATED, &p1) == HM_OK);
    CHECK(hm_make_packet(&hm, 200u, TM_ORIGIN_SIMULATED, &p2) == HM_OK);
    CHECK(p1.sequence == 0u && p2.sequence == 1u);
    CHECK(p1.mode == TM_MODE_NOMINAL);
    CHECK(p1.fault_flags == HM_FAULT_BATT_LOW);
    CHECK(p1.battery_mv == 7100u && p1.temperature_cdeg == 2150);
    CHECK(p1.mission_time_ms == 100u && p1.origin == TM_ORIGIN_SIMULATED);
    CHECK(tm_encode(&p1, buf, sizeof buf) == TM_OK);
    CHECK(tm_decode(buf, sizeof buf, &back) == TM_OK);
    CHECK(back.fault_flags == HM_FAULT_BATT_LOW && back.mode == TM_MODE_NOMINAL);

    hm.sequence = 0xFFFFu;
    hm_make_packet(&hm, 300u, TM_ORIGIN_SIMULATED, &p1);
    hm_make_packet(&hm, 400u, TM_ORIGIN_SIMULATED, &p2);
    CHECK(p1.sequence == 0xFFFFu && p2.sequence == 0u);
}

static void test_null_pointers_are_rejected(void)
{
    hm_t hm;
    hm_inputs_t in = reading(8000u, 2000, 1u);
    tm_packet_t p;
    hm_init(&hm, 0u);
    CHECK(hm_init(NULL, 0u) == HM_ERR_NULL);
    CHECK(hm_kick(NULL, 0u) == HM_ERR_NULL);
    CHECK(hm_update(NULL, &in, 0u) == HM_ERR_NULL);
    CHECK(hm_update(&hm, NULL, 0u) == HM_ERR_NULL);
    CHECK(hm_command(NULL, HM_CMD_GOTO_SAFE) == HM_ERR_NULL);
    CHECK(hm_make_packet(NULL, 0u, TM_ORIGIN_SIMULATED, &p) == HM_ERR_NULL);
    CHECK(hm_make_packet(&hm, 0u, TM_ORIGIN_SIMULATED, NULL) == HM_ERR_NULL);
}

int main(void)
{
    test_starts_in_safe_and_stays_latched();
    test_command_paths();
    test_low_battery_demotes_observation();
    test_critical_battery_forces_safe_and_needs_a_command();
    test_battery_hysteresis();
    test_temperature_thresholds_and_hysteresis();
    test_invalid_and_out_of_range_sensors_are_faults();
    test_watchdog_timeout_and_recovery();
    test_watchdog_survives_counter_wrap();
    test_packet_carries_state_and_round_trips();
    test_null_pointers_are_rejected();
    printf("%d checks, %d failed\n", g_checks, g_failed);
    return g_failed == 0 ? 0 : 1;
}