#ifndef MONITOR_H
#define MONITOR_H

#include "hal.h"
#include "health.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum { MON_OK = 0, MON_ERR_NULL, MON_ERR_HAL_INCOMPLETE } mon_status_t;

/* One monitoring cycle: read time and sensors through the HAL, update the health
   monitor (the watchdog is checked against the PREVIOUS heartbeat), then send the
   new heartbeat to the monitor and the hardware watchdog.
   A failed sensor read sets the SENSOR_INVALID fault; the last good values are kept.
   If the HAL is incomplete, nothing is changed. */
mon_status_t mon_step(hm_t *hm, const hal_t *hal);

#ifdef __cplusplus
}
#endif

#endif /* MONITOR_H */