#include <stdio.h>

#include "health.h"

typedef struct {
    uint32_t t_ms;        /* mission time of this step, ms */
    uint8_t kick;         /* 1 = heartbeat arrives before the update */
    uint8_t valid;        /* 0 = sampling hardware reports failure */
    uint16_t batt_mv;     /* millivolts */
    int16_t temp_cdeg;    /* 0.01 degC */
    int cmd;              /* -1 = none, otherwise an hm_cmd_t */
    hm_status_t expected; /* expected result of the command */
} step_t;

static const step_t STEPS[] = {
    {  100u, 1u, 1u, 8000u, 2000, -1,                        HM_OK },
    {  200u, 1u, 1u, 8000u, 2000, HM_CMD_GOTO_NOMINAL,       HM_OK },
    {  300u, 1u, 1u, 8000u, 2000, HM_CMD_GOTO_OBSERVATION,   HM_OK },
    {  400u, 1u, 1u, 6900u, 2000, -1,                        HM_OK },
    {  500u, 1u, 1u, 6700u, 2000, HM_CMD_GOTO_NOMINAL,       HM_ERR_REJECTED },
    {  600u, 1u, 1u, 7000u, 2000, -1,                        HM_OK },
    {  700u, 1u, 1u, 7400u, 2000, -1,                        HM_OK },
    {  800u, 1u, 1u, 8000u, 2000, HM_CMD_GOTO_NOMINAL,       HM_OK },
    { 6000u, 0u, 1u, 8000u, 2000, -1,                        HM_OK },
    { 6100u, 1u, 1u, 8000u, 2000, -1,                        HM_OK },
    { 6200u, 1u, 0u, 1234u,  100, -1,                        HM_OK }
};

#define N_STEPS (sizeof STEPS / sizeof STEPS[0])

int main(int argc, char **argv)
{
    FILE *f;
    hm_t hm;
    size_t i;
    int failed = 0;

    if (argc != 2) {
        fprintf(stderr, "usage: emit_scenario <output-file>\n");
        return 2;
    }
    f = fopen(argv[1], "wb");
    if (f == NULL) {
        fprintf(stderr, "cannot open output file\n");
        return 2;
    }
    (void)hm_init(&hm, 0u);

    for (i = 0; i < N_STEPS; i++) {
        hm_inputs_t in;
        tm_packet_t p;
        uint8_t buf[TM_PACKET_SIZE];

        if (STEPS[i].kick) (void)hm_kick(&hm, STEPS[i].t_ms);
        in.battery_mv = STEPS[i].batt_mv;
        in.temperature_cdeg = STEPS[i].temp_cdeg;
        in.sensors_valid = STEPS[i].valid;
        (void)hm_update(&hm, &in, STEPS[i].t_ms);

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