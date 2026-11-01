#include "health.h"

static uint16_t apply_flag(uint16_t flags, uint16_t bit, int set_cond, int clear_cond)
{
    if (set_cond) return (uint16_t)(flags | bit);
    if (clear_cond) return (uint16_t)(flags & (uint16_t)~bit);
    return flags;
}

hm_status_t hm_init(hm_t *hm, uint32_t now_ms)
{
    if (hm == NULL) return HM_ERR_NULL;
    hm->mode = (uint8_t)TM_MODE_SAFE;
    hm->faults = 0u;
    hm->last_kick_ms = now_ms;
    hm->sequence = 0u;
    hm->battery_mv = 0u;
    hm->temperature_cdeg = 0;
    return HM_OK;
}

hm_status_t hm_kick(hm_t *hm, uint32_t now_ms)
{
    if (hm == NULL) return HM_ERR_NULL;
    hm->last_kick_ms = now_ms;
    return HM_OK;
}

hm_status_t hm_update(hm_t *hm, const hm_inputs_t *in, uint32_t now_ms)
{
    uint16_t f;
    int valid;
    uint32_t elapsed;

    if (hm == NULL || in == NULL) return HM_ERR_NULL;
    f = hm->faults;

    valid = (in->sensors_valid != 0u) &&
            (in->battery_mv <= TM_BATTERY_MAX_MV) &&
            (in->temperature_cdeg >= TM_TEMP_MIN_CDEG) &&
            (in->temperature_cdeg <= TM_TEMP_MAX_CDEG);

    if (valid) {
        hm->battery_mv = in->battery_mv;
        hm->temperature_cdeg = in->temperature_cdeg;
        f = apply_flag(f, HM_FAULT_SENSOR_INVALID, 0, 1);
        f = apply_flag(f, HM_FAULT_BATT_CRITICAL,
                       in->battery_mv < HM_BATT_CRITICAL_MV,
                       in->battery_mv >= HM_BATT_CRITICAL_MV + HM_BATT_HYST_MV);
        f = apply_flag(f, HM_FAULT_BATT_LOW,
                       in->battery_mv < HM_BATT_LOW_MV,
                       in->battery_mv >= HM_BATT_LOW_MV + HM_BATT_HYST_MV);
        f = apply_flag(f, HM_FAULT_TEMP_HIGH,
                       in->temperature_cdeg > HM_TEMP_HIGH_CDEG,
                       in->temperature_cdeg <= HM_TEMP_HIGH_CDEG - HM_TEMP_HYST_CDEG);
        f = apply_flag(f, HM_FAULT_TEMP_LOW,
                       in->temperature_cdeg < HM_TEMP_LOW_CDEG,
                       in->temperature_cdeg >= HM_TEMP_LOW_CDEG + HM_TEMP_HYST_CDEG);
    } else {
        f = apply_flag(f, HM_FAULT_SENSOR_INVALID, 1, 0);
    }

    elapsed = now_ms - hm->last_kick_ms; /* unsigned: correct across wrap-around */
    f = apply_flag(f, HM_FAULT_WATCHDOG,
                   elapsed > HM_WATCHDOG_TIMEOUT_MS,
                   elapsed <= HM_WATCHDOG_TIMEOUT_MS);

    hm->faults = f;
    if ((f & HM_CRITICAL_MASK) != 0u) {
        hm->mode = (uint8_t)TM_MODE_SAFE;
    } else if (hm->mode == TM_MODE_OBSERVATION && (f & HM_DEGRADED_MASK) != 0u) {
        hm->mode = (uint8_t)TM_MODE_NOMINAL;
    }
    return HM_OK;
}

hm_status_t hm_command(hm_t *hm, hm_cmd_t cmd)
{
    if (hm == NULL) return HM_ERR_NULL;
    switch (cmd) {
    case HM_CMD_GOTO_SAFE:
        hm->mode = (uint8_t)TM_MODE_SAFE;
        return HM_OK;
    case HM_CMD_GOTO_NOMINAL:
        if ((hm->faults & HM_CRITICAL_MASK) != 0u) return HM_ERR_REJECTED;
        hm->mode = (uint8_t)TM_MODE_NOMINAL;
        return HM_OK;
    case HM_CMD_GOTO_OBSERVATION:
        if (hm->mode != TM_MODE_NOMINAL || hm->faults != 0u) return HM_ERR_REJECTED;
        hm->mode = (uint8_t)TM_MODE_OBSERVATION;
        return HM_OK;
    default:
        return HM_ERR_INVALID_CMD;
    }
}

hm_status_t hm_make_packet(hm_t *hm, uint32_t now_ms, uint8_t origin, tm_packet_t *out)
{
    if (hm == NULL || out == NULL) return HM_ERR_NULL;
    out->sequence = hm->sequence;
    hm->sequence = (uint16_t)(hm->sequence + 1u);
    out->mission_time_ms = now_ms;
    out->battery_mv = hm->battery_mv;
    out->temperature_cdeg = hm->temperature_cdeg;
    out->mode = hm->mode;
    out->fault_flags = hm->faults;
    out->origin = origin;
    return HM_OK;
}