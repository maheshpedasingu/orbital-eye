#include <stddef.h>

#include "hal_sim.h"

static hal_status_t sim_read_battery(void *ctx, uint16_t *out)
{
    hal_sim_t *s = (hal_sim_t *)ctx;
    if (s == NULL || out == NULL) return HAL_ERR_NULL;
    if (s->fail_battery != 0) return HAL_ERR_IO;
    *out = s->battery_mv;
    return HAL_OK;
}

static hal_status_t sim_read_temperature(void *ctx, int16_t *out)
{
    hal_sim_t *s = (hal_sim_t *)ctx;
    if (s == NULL || out == NULL) return HAL_ERR_NULL;
    if (s->fail_temperature != 0) return HAL_ERR_IO;
    *out = s->temperature_cdeg;
    return HAL_OK;
}

static uint32_t sim_now_ms(void *ctx)
{
    const hal_sim_t *s = (const hal_sim_t *)ctx;
    return (s != NULL) ? s->now_ms : 0u;
}

static void sim_kick(void *ctx)
{
    hal_sim_t *s = (hal_sim_t *)ctx;
    if (s != NULL) s->hw_kicks++;
}

void hal_sim_init(hal_sim_t *sim, uint32_t now_ms, uint16_t batt_mv, int16_t temp_cdeg)
{
    if (sim == NULL) return;
    sim->now_ms = now_ms;
    sim->battery_mv = batt_mv;
    sim->temperature_cdeg = temp_cdeg;
    sim->fail_battery = 0;
    sim->fail_temperature = 0;
    sim->hw_kicks = 0u;
}

hal_t hal_sim_make(hal_sim_t *sim)
{
    hal_t h;
    h.ctx = sim;
    h.read_battery_mv = sim_read_battery;
    h.read_temperature_cdeg = sim_read_temperature;
    h.now_ms = sim_now_ms;
    h.kick_hw_watchdog = sim_kick;
    return h;
}