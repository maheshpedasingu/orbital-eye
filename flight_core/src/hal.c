#include <stddef.h>

#include "hal.h"

int hal_is_complete(const hal_t *hal)
{
    if (hal == NULL) return 0;
    if (hal->read_battery_mv == NULL) return 0;
    if (hal->read_temperature_cdeg == NULL) return 0;
    if (hal->now_ms == NULL) return 0;
    if (hal->kick_hw_watchdog == NULL) return 0;
    return 1;
}