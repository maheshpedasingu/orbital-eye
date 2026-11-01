#include <stdio.h>

#include "telemetry.h"

static tm_packet_t make(uint16_t seq, uint32_t time_ms, uint16_t batt_mv,
                        int16_t temp_cdeg, uint8_t mode, uint16_t faults,
                        uint8_t origin)
{
    tm_packet_t p;
    p.sequence = seq;
    p.mission_time_ms = time_ms;
    p.battery_mv = batt_mv;
    p.temperature_cdeg = temp_cdeg;
    p.mode = mode;
    p.fault_flags = faults;
    p.origin = origin;
    return p;
}

static int emit(FILE *f, tm_packet_t p)
{
    uint8_t buf[TM_PACKET_SIZE];
    if (tm_encode(&p, buf, sizeof buf) != TM_OK) return 1;
    if (fwrite(buf, 1, sizeof buf, f) != sizeof buf) return 1;
    return 0;
}

int main(int argc, char **argv)
{
    FILE *f;
    int failed = 0;

    if (argc != 2) {
        fprintf(stderr, "usage: emit_packets <output-file>\n");
        return 2;
    }
    f = fopen(argv[1], "wb");
    if (f == NULL) {
        fprintf(stderr, "cannot open output file\n");
        return 2;
    }

    failed |= emit(f, make(0x0102u, 0x0A0B0C0Du, 8000u, -250,
                           TM_MODE_NOMINAL, 0x0003u, TM_ORIGIN_SIMULATED));
    failed |= emit(f, make(0u, 0u, 0u, TM_TEMP_MIN_CDEG,
                           TM_MODE_SAFE, 0u, TM_ORIGIN_SPACECRAFT));
    failed |= emit(f, make(0xFFFFu, 0xFFFFFFFFu, TM_BATTERY_MAX_MV, TM_TEMP_MAX_CDEG,
                           TM_MODE_OBSERVATION, 0xFFFFu, TM_ORIGIN_SIMULATED));
    failed |= emit(f, make(1u, 1000u, 7400u, 2150,
                           TM_MODE_NOMINAL, 0u, TM_ORIGIN_SIMULATED));

    if (fclose(f) != 0) failed = 1;
    return failed;
}