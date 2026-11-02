#include <stddef.h>

#include "monitor.h"

mon_status_t mon_step(hm_t *hm, const hal_t *hal)
{
    hm_inputs_t in;
    uint32_t now;
    uint16_t batt = 0u;
    int16_t temp = 0;
    int ok = 1;

    if (hm == NULL || hal == NULL) return MON_ERR_NULL;
    if (!hal_is_complete(hal)) return MON_ERR_HAL_INCOMPLETE;

    now = hal->now_ms(hal->ctx);
    if (hal->read_battery_mv(hal->ctx, &batt) != HAL_OK) ok = 0;
    if (hal->read_temperature_cdeg(hal->ctx, &temp) != HAL_OK) ok = 0;

    in.battery_mv = batt;
    in.temperature_cdeg = temp;
    in.sensors_valid = (uint8_t)(ok ? 1u : 0u);

    (void)hm_update(hm, &in, now);  /* checks the watchdog against the previous heartbeat */
    (void)hm_kick(hm, now);         /* then records this cycle as the new heartbeat */
    hal->kick_hw_watchdog(hal->ctx);
    return MON_OK;
}