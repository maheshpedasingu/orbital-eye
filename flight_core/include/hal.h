#ifndef HAL_H
#define HAL_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum { HAL_OK = 0, HAL_ERR_NULL, HAL_ERR_IO } hal_status_t;

/* Every function receives the ctx pointer stored in the hal_t. A real board provides
   register-level implementations; hal_sim.h provides a simulated one. */
typedef struct {
    void *ctx;
    hal_status_t (*read_battery_mv)(void *ctx, uint16_t *out);       /* millivolts */
    hal_status_t (*read_temperature_cdeg)(void *ctx, int16_t *out);  /* 0.01 degC */
    uint32_t     (*now_ms)(void *ctx);                               /* milliseconds, wraps at 2^32 */
    void         (*kick_hw_watchdog)(void *ctx);
} hal_t;

/* Returns 1 if hal is non-NULL and all four function pointers are set, else 0. */
int hal_is_complete(const hal_t *hal);

#ifdef __cplusplus
}
#endif

#endif /* HAL_H */