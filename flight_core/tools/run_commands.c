#include <stdio.h>

#include "command.h"
#include "health.h"

/* Reads a file of back-to-back 8-byte command packets, feeds each one to the real
   receiver, and prints "index STATUS MODE" per packet. The monitor starts healthy. */

static const char *mode_name(uint8_t m)
{
    switch (m) {
    case TM_MODE_SAFE:        return "SAFE";
    case TM_MODE_NOMINAL:     return "NOMINAL";
    case TM_MODE_OBSERVATION: return "OBSERVATION";
    default:                  return "INVALID";
    }
}

int main(int argc, char **argv)
{
    FILE *f;
    hm_t hm;
    cmd_rx_t rx;
    hm_inputs_t in;
    uint8_t buf[CMD_PACKET_SIZE];
    unsigned index = 0u;
    size_t n;

    if (argc != 2) {
        fprintf(stderr, "usage: run_commands <packet-file>\n");
        return 2;
    }
    f = fopen(argv[1], "rb");
    if (f == NULL) {
        fprintf(stderr, "cannot open input file\n");
        return 2;
    }

    (void)hm_init(&hm, 100u);
    in.battery_mv = 8000u;
    in.temperature_cdeg = 2000;
    in.sensors_valid = 1u;
    (void)hm_update(&hm, &in, 100u);
    cmd_rx_init(&rx, 0u);

    while ((n = fread(buf, 1, sizeof buf, f)) == sizeof buf) {
        cmd_status_t st = cmd_rx_process(&rx, &hm, buf, sizeof buf);
        printf("%u %s %s\n", index, cmd_status_name(st), mode_name(hm.mode));
        index++;
    }
    if (n != 0u) {
        fprintf(stderr, "trailing partial packet\n");
        fclose(f);
        return 2;
    }
    fclose(f);
    return 0;
}