#ifndef HEALTH_H
#define HEALTH_H

#include <stdint.h>

#include "telemetry.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Fault flag bits, carried in the telemetry fault_flags field */
#define HM_FAULT_BATT_LOW        0x0001u
#define HM_FAULT_BATT_CRITICAL   0x0002u
#define HM_FAULT_TEMP_HIGH       0x0004u
#define HM_FAULT_TEMP_LOW        0x0008u
#define HM_FAULT_WATCHDOG        0x0010u
#define HM_FAULT_SENSOR_INVALID  0x0020u

/* Faults that force SAFE immediately */
#define HM_CRITICAL_MASK (HM_FAULT_BATT_CRITICAL | HM_FAULT_TEMP_HIGH | \
                          HM_FAULT_WATCHDOG | HM_FAULT_SENSOR_INVALID)
/* Faults that stop OBSERVATION but allow NOMINAL */
#define HM_DEGRADED_MASK (HM_FAULT_BATT_LOW | HM_FAULT_TEMP_LOW)

/* Thresholds (illustrative, not from any real spacecraft) */
#define HM_BATT_LOW_MV 7200        /* millivolts */
#define HM_BATT_CRITICAL_MV 6800   /* millivolts */
#define HM_BATT_HYST_MV 200        /* millivolts */
#define HM_TEMP_HIGH_CDEG 6000     /* 0.01 degC */
#define HM_TEMP_LOW_CDEG (-1000)   /* 0.01 degC */
#define HM_TEMP_HYST_CDEG 500      /* 0.01 degC */
#define HM_WATCHDOG_TIMEOUT_MS 5000u

typedef enum {
    HM_OK = 0,
    HM_ERR_NULL,
    HM_ERR_REJECTED,
    HM_ERR_INVALID_CMD
} hm_status_t;

typedef enum {
    HM_CMD_GOTO_SAFE = 0,
    HM_CMD_GOTO_NOMINAL,
    HM_CMD_GOTO_OBSERVATION
} hm_cmd_t;

typedef struct {
    uint16_t battery_mv;        /* millivolts */
    int16_t  temperature_cdeg;  /* 0.01 degC */
    uint8_t  sensors_valid;     /* 0 = the sampling hardware reports a failure */
} hm_inputs_t;

typedef struct {
    uint8_t  mode;              /* tm_mode_t */
    uint16_t faults;            /* HM_FAULT_* bits */
    uint32_t last_kick_ms;      /* time of the last heartbeat */
    uint16_t sequence;          /* next telemetry sequence number */
    uint16_t battery_mv;        /* last VALID reading (stale if SENSOR_INVALID) */
    int16_t  temperature_cdeg;  /* last VALID reading (stale if SENSOR_INVALID) */
} hm_t;

hm_status_t hm_init(hm_t *hm, uint32_t now_ms);
hm_status_t hm_kick(hm_t *hm, uint32_t now_ms);
hm_status_t hm_update(hm_t *hm, const hm_inputs_t *in, uint32_t now_ms);
hm_status_t hm_command(hm_t *hm, hm_cmd_t cmd);

/* Fills *out from the current state and advances the sequence number. */
hm_status_t hm_make_packet(hm_t *hm, uint32_t now_ms, uint8_t origin, tm_packet_t *out);

#ifdef __cplusplus
}
#endif

#endif /* HEALTH_H */