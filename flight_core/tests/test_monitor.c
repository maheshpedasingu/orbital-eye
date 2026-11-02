#include <stdio.h>

#include "hal_sim.h"
#include "health.h"
#include "monitor.h"
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

static void run_step(hm_t *hm, hal_sim_t *sim, const hal_t *hal, uint32_t t_ms)
{
    sim->now_ms = t_ms;
    (void)mon_step(hm, hal);
}

static void test_steady_stepping_never_trips_the_watchdog(void)
{
    hm_t hm;
    hal_sim_t sim;
    hal_t hal;
    uint32_t t;

    hal_sim_init(&sim, 0u, 8000u, 2000);
    hal = hal_sim_make(&sim);
    hm_init(&hm, 0u);
    for (t = 1000u; t <= 20000u; t += 1000u) {
        sim.now_ms = t;
        CHECK(mon_step(&hm, &hal) == MON_OK);
    }
    CHECK(hm.faults == 0u);
    CHECK(sim.hw_kicks == 20u);   /* one hardware kick per cycle */
}

static void test_a_stalled_loop_is_detected_exactly_past_the_limit(void)
{
    hm_t hm;
    hal_sim_t sim;
    hal_t hal;

    hal_sim_init(&sim, 0u, 8000u, 2000);
    hal = hal_sim_make(&sim);
    hm_init(&hm, 0u);
    run_step(&hm, &sim, &hal, 1000u);
    run_step(&hm, &sim, &hal, 6000u);            /* 5000 ms since the last cycle */
    CHECK((hm.faults & HM_FAULT_WATCHDOG) == 0u);
    run_step(&hm, &sim, &hal, 11001u);           /* 5001 ms since the last cycle */
    CHECK((hm.faults & HM_FAULT_WATCHDOG) != 0u);
    CHECK(hm.mode == TM_MODE_SAFE);
    run_step(&hm, &sim, &hal, 11100u);           /* cycling again: fault clears */
    CHECK(hm.faults == 0u);
    CHECK(hm.mode == TM_MODE_SAFE);              /* SAFE stays latched */
}

static void test_failed_battery_read_sets_sensor_invalid_and_keeps_last_value(void)
{
    hm_t hm;
    hal_sim_t sim;
    hal_t hal;

    hal_sim_init(&sim, 0u, 8000u, 2000);
    hal = hal_sim_make(&sim);
    hm_init(&hm, 0u);
    run_step(&hm, &sim, &hal, 100u);
    CHECK(hm_command(&hm, HM_CMD_GOTO_NOMINAL) == HM_OK);

    sim.fail_battery = 1;
    sim.battery_mv = 1234u;                      /* must NOT be used */
    run_step(&hm, &sim, &hal, 200u);
    CHECK((hm.faults & HM_FAULT_SENSOR_INVALID) != 0u);
    CHECK(hm.mode == TM_MODE_SAFE);
    CHECK(hm.battery_mv == 8000u);

    sim.fail_battery = 0;
    sim.battery_mv = 8000u;
    run_step(&hm, &sim, &hal, 300u);
    CHECK((hm.faults & HM_FAULT_SENSOR_INVALID) == 0u);
    CHECK(hm.mode == TM_MODE_SAFE);              /* latched until commanded */
}

static void test_failed_temperature_read_sets_sensor_invalid(void)
{
    hm_t hm;
    hal_sim_t sim;
    hal_t hal;

    hal_sim_init(&sim, 0u, 8000u, 2000);
    hal = hal_sim_make(&sim);
    hm_init(&hm, 0u);
    sim.fail_temperature = 1;
    run_step(&hm, &sim, &hal, 100u);
    CHECK((hm.faults & HM_FAULT_SENSOR_INVALID) != 0u);
    CHECK(hm.temperature_cdeg == 0);             /* never stored a good value */
}

static void test_critical_battery_through_the_hal_forces_safe(void)
{
    hm_t hm;
    hal_sim_t sim;
    hal_t hal;

    hal_sim_init(&sim, 0u, 6700u, 2000);
    hal = hal_sim_make(&sim);
    hm_init(&hm, 0u);
    run_step(&hm, &sim, &hal, 100u);
    CHECK((hm.faults & HM_FAULT_BATT_CRITICAL) != 0u);
    CHECK((hm.faults & HM_FAULT_BATT_LOW) != 0u);
    CHECK(hm.mode == TM_MODE_SAFE);
    CHECK(hm_command(&hm, HM_CMD_GOTO_NOMINAL) == HM_ERR_REJECTED);
}

static void test_counter_wrap_around_through_the_hal(void)
{
    hm_t hm;
    hal_sim_t sim;
    hal_t hal;

    hal_sim_init(&sim, 0xFFFFFF00u, 8000u, 2000);
    hal = hal_sim_make(&sim);
    hm_init(&hm, 0xFFFFFF00u);
    run_step(&hm, &sim, &hal, 0xFFFFFF00u);
    run_step(&hm, &sim, &hal, 0x000000FFu);      /* 511 ms later, across the wrap */
    CHECK((hm.faults & HM_FAULT_WATCHDOG) == 0u);
    run_step(&hm, &sim, &hal, 0x00001500u);      /* 5121 ms after the last cycle */
    CHECK((hm.faults & HM_FAULT_WATCHDOG) != 0u);
}

static void test_incomplete_hal_is_refused_and_changes_nothing(void)
{
    hm_t hm;
    hal_sim_t sim;
    hal_t good;
    hal_t bad;

    hal_sim_init(&sim, 5000u, 8000u, 2000);
    good = hal_sim_make(&sim);
    hm_init(&hm, 0u);

    CHECK(hal_is_complete(&good) == 1);
    CHECK(hal_is_complete(NULL) == 0);
    bad = good; bad.now_ms = NULL;
    CHECK(mon_step(&hm, &bad) == MON_ERR_HAL_INCOMPLETE);
    bad = good; bad.read_battery_mv = NULL;
    CHECK(mon_step(&hm, &bad) == MON_ERR_HAL_INCOMPLETE);
    bad = good; bad.read_temperature_cdeg = NULL;
    CHECK(mon_step(&hm, &bad) == MON_ERR_HAL_INCOMPLETE);
    bad = good; bad.kick_hw_watchdog = NULL;
    CHECK(mon_step(&hm, &bad) == MON_ERR_HAL_INCOMPLETE);
    CHECK(hm.faults == 0u);
    CHECK(sim.hw_kicks == 0u);
}

static void test_null_arguments_are_rejected(void)
{
    hm_t hm;
    hal_sim_t sim;
    hal_t hal;

    hal_sim_init(&sim, 0u, 8000u, 2000);
    hal = hal_sim_make(&sim);
    hm_init(&hm, 0u);
    CHECK(mon_step(NULL, &hal) == MON_ERR_NULL);
    CHECK(mon_step(&hm, NULL) == MON_ERR_NULL);
}

static void test_packet_built_from_hal_driven_state_round_trips(void)
{
    hm_t hm;
    hal_sim_t sim;
    hal_t hal;
    tm_packet_t p;
    tm_packet_t back;
    uint8_t buf[TM_PACKET_SIZE];

    hal_sim_init(&sim, 0u, 7100u, 2150);
    hal = hal_sim_make(&sim);
    hm_init(&hm, 0u);
    run_step(&hm, &sim, &hal, 100u);
    CHECK(hm_command(&hm, HM_CMD_GOTO_NOMINAL) == HM_OK);
    CHECK(hm_make_packet(&hm, 100u, TM_ORIGIN_SIMULATED, &p) == HM_OK);
    CHECK(p.battery_mv == 7100u && p.temperature_cdeg == 2150);
    CHECK(p.fault_flags == HM_FAULT_BATT_LOW && p.mode == TM_MODE_NOMINAL);
    CHECK(tm_encode(&p, buf, sizeof buf) == TM_OK);
    CHECK(tm_decode(buf, sizeof buf, &back) == TM_OK);
    CHECK(back.battery_mv == 7100u && back.mode == TM_MODE_NOMINAL);
}

int main(void)
{
    test_steady_stepping_never_trips_the_watchdog();
    test_a_stalled_loop_is_detected_exactly_past_the_limit();
    test_failed_battery_read_sets_sensor_invalid_and_keeps_last_value();
    test_failed_temperature_read_sets_sensor_invalid();
    test_critical_battery_through_the_hal_forces_safe();
    test_counter_wrap_around_through_the_hal();
    test_incomplete_hal_is_refused_and_changes_nothing();
    test_null_arguments_are_rejected();
    test_packet_built_from_hal_driven_state_round_trips();
    printf("%d checks, %d failed\n", g_checks, g_failed);
    return g_failed == 0 ? 0 : 1;
}