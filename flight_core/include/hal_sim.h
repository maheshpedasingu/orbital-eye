#ifndef HAL_SIM_H
#define HAL_SIM_H

#include <stdint.h>

#include "hal.h"

#ifdef __cplusplus
extern "C" {
#endif

/* A SIMULATED board. Nothing here talks to real hardware. */
typedef struct {
    uint32_t now_ms;           /* milliseconds */
    uint16_t battery_mv;       /* millivolts */
    int16_t  temperature_cdeg; /* 0.01 degC */
    int      fail_battery;     /* nonzero: battery reads return HAL_ERR_IO */
    int      fail_temperature; /* nonzero: temperature reads return HAL_ERR_IO */
    unsigned hw_kicks;         /* number of hardware watchdog kicks so far */
} hal_sim_t;

void hal_sim_init(hal_sim_t *sim, uint32_t now_ms, uint16_t batt_mv, int16_t temp_cdeg);

/* Builds a hal_t whose ctx is sim. sim must outlive the returned struct. */
hal_t hal_sim_make(hal_sim_t *sim);

#ifdef __cplusplus
}
#endif

#endif /* HAL_SIM_H */