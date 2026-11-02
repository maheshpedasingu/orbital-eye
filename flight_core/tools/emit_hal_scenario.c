#include <stdio.h>

#include "hal_sim.h"
#include "health.h"
#include "monitor.h"
#include "telemetry.h"

/* The same 11-step scenario as emit_scenario.c, but driven through the HAL.
   Each row is one monitoring cycle at the given mission time. */
typedef struct {
    uint32_t t_ms;         /* mission time, ms */
    uint16_t batt_mv;      /* millivolts */
    int16_t temp_cdeg;     /* 0.01 degC */
    int fail_battery;      /* 1 = the battery read fails this cycle */
    int cmd;               /* -1 = none, otherwise an hm_cmd_t */
    hm_status_t expected;  /* expected result of the command */
} step_t;

static const step_t STEPS[] = {
    {  100u, 8000u, 2000, 0, -1,                      HM_OK },
    {  200u, 8000u, 2000, 0, HM_CMD_GOTO_NOMINAL,     HM_OK },
    {  300u, 8000u, 2000, 0, HM_CMD_GOTO_OBSERVATION, HM_OK },
    {  400u, 6900u, 2000, 0, -1,                      HM_OK },
    {  500u, 6700u, 2000, 0, HM_CMD_GOTO_NOMINAL,     HM_ERR_REJECTED },
    {  600u, 7000u, 2000, 0, -1,                      HM_OK },
    {  700u, 7400u, 2000, 0, -1,                      HM_OK },
    {  800u, 8000u, 2000, 0, HM_CMD_GOTO_NOMINAL,     HM_OK },
    { 6000u, 8000u, 2000, 0, -1,                      HM_OK },
    { 6100u, 8000u, 2000, 0, -1,                      HM_OK },
    { 6200u, 8000u, 2000, 1, -1,                      HM_OK }
};

#define N_STEPS (sizeof STEPS / sizeof STEPS[0])

int main(int argc, char **argv)
{
    FILE *f;
    hm_t hm;
    hal_sim_t sim;
    hal_t hal;
    size_t i;
    int failed = 0;

    if (argc != 2) {
        fprintf(stderr, "usage: emit_hal_scenario <output-file>\n");
        return 2;
    }
    f = fopen(argv[1], "wb");
    if (f == NULL) {
        fprintf(stderr, "cannot open output file\n");
        return 2;
    }
    hal_sim_init(&sim, 0u, 8000u, 2000);
    hal = hal_sim_make(&sim);
    (void)hm_init(&hm, 0u);

    for (i = 0; i < N_STEPS; i++) {
        tm_packet_t p;
        uint8_t buf[TM_PACKET_SIZE];

        sim.now_ms = STEPS[i].t_ms;
        sim.battery_mv = STEPS[i].batt_mv;
        sim.temperature_cdeg = STEPS[i].temp_cdeg;
        sim.fail_battery = STEPS[i].fail_battery;
        if (mon_step(&hm, &hal) != MON_OK) {
            fprintf(stderr, "step %u: monitor step failed\n", (unsigned)i);
            failed = 1;
        }

        if (STEPS[i].cmd >= 0) {
            hm_status_t st = hm_command(&hm, (hm_cmd_t)STEPS[i].cmd);
            if (st != STEPS[i].expected) {
                fprintf(stderr, "step %u: command result %d, expected %d\n",
                        (unsigned)i, (int)st, (int)STEPS[i].expected);
                failed = 1;
            }
        }

        if (hm_make_packet(&hm, STEPS[i].t_ms, TM_ORIGIN_SIMULATED, &p) != HM_OK ||
            tm_encode(&p, buf, sizeof buf) != TM_OK ||
            fwrite(buf, 1, sizeof buf, f) != sizeof buf) {
            fprintf(stderr, "step %u: could not write packet\n", (unsigned)i);
            failed = 1;
        }
    }

    if (fclose(f) != 0) failed = 1;
    return failed;
}