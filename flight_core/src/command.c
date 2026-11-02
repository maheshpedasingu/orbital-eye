#include "command.h"

static void put_u16(uint8_t *p, uint16_t v)
{
    p[0] = (uint8_t)(v & 0xFFu);
    p[1] = (uint8_t)((v >> 8) & 0xFFu);
}

static uint16_t get_u16(const uint8_t *p)
{
    return (uint16_t)((uint16_t)p[0] | (uint16_t)((uint16_t)p[1] << 8));
}

cmd_status_t cmd_encode(const cmd_packet_t *pkt, uint8_t *buf, size_t buf_len)
{
    if (pkt == NULL || buf == NULL) return CMD_ERR_NULL;
    if (buf_len < CMD_PACKET_SIZE) return CMD_ERR_LENGTH;
    if (pkt->command > CMD_ID_MAX) return CMD_ERR_RANGE;

    put_u16(buf + 0, CMD_SYNC_WORD);
    buf[2] = (uint8_t)CMD_VERSION;
    put_u16(buf + 3, pkt->sequence);
    buf[5] = pkt->command;
    put_u16(buf + 6, tm_crc16(buf, CMD_PACKET_SIZE - 2u));
    return CMD_OK;
}

cmd_status_t cmd_decode(const uint8_t *buf, size_t buf_len, cmd_packet_t *out)
{
    if (buf == NULL || out == NULL) return CMD_ERR_NULL;
    if (buf_len != CMD_PACKET_SIZE) return CMD_ERR_LENGTH;
    if (get_u16(buf) != CMD_SYNC_WORD) return CMD_ERR_SYNC;
    if (buf[2] != CMD_VERSION) return CMD_ERR_VERSION;
    if (get_u16(buf + 6) != tm_crc16(buf, CMD_PACKET_SIZE - 2u)) return CMD_ERR_CRC;
    if (buf[5] > CMD_ID_MAX) return CMD_ERR_RANGE;

    out->sequence = get_u16(buf + 3);
    out->command = buf[5];
    return CMD_OK;
}

void cmd_rx_init(cmd_rx_t *rx, uint16_t last_seq)
{
    if (rx == NULL) return;
    rx->last_seq = last_seq;
    rx->n_executed = 0u;
    rx->n_refused = 0u;
    rx->n_invalid = 0u;
}

cmd_status_t cmd_rx_process(cmd_rx_t *rx, hm_t *hm, const uint8_t *buf, size_t buf_len)
{
    cmd_packet_t pkt;
    cmd_status_t st;
    uint16_t delta;
    hm_cmd_t hcmd;

    if (rx == NULL || hm == NULL) return CMD_ERR_NULL;

    st = cmd_decode(buf, buf_len, &pkt);
    if (st != CMD_OK) {
        rx->n_invalid++;
        return st;
    }

    delta = (uint16_t)(pkt.sequence - rx->last_seq);   /* modular distance ahead */
    if (delta == 0u || delta > CMD_SEQ_WINDOW) {
        rx->n_invalid++;
        return CMD_ERR_SEQUENCE;
    }
    rx->last_seq = pkt.sequence;                       /* consumed from here on */

    switch (pkt.command) {
    case CMD_ID_GOTO_SAFE:        hcmd = HM_CMD_GOTO_SAFE;        break;
    case CMD_ID_GOTO_NOMINAL:     hcmd = HM_CMD_GOTO_NOMINAL;     break;
    case CMD_ID_GOTO_OBSERVATION: hcmd = HM_CMD_GOTO_OBSERVATION; break;
    default:
        rx->n_invalid++;
        return CMD_ERR_RANGE;
    }

    if (hm_command(hm, hcmd) != HM_OK) {
        rx->n_refused++;
        return CMD_ERR_REFUSED;
    }
    rx->n_executed++;
    return CMD_OK;
}

const char *cmd_status_name(cmd_status_t st)
{
    switch (st) {
    case CMD_OK:           return "OK";
    case CMD_ERR_NULL:     return "NULL";
    case CMD_ERR_LENGTH:   return "LENGTH";
    case CMD_ERR_SYNC:     return "SYNC";
    case CMD_ERR_VERSION:  return "VERSION";
    case CMD_ERR_CRC:      return "CRC";
    case CMD_ERR_RANGE:    return "RANGE";
    case CMD_ERR_SEQUENCE: return "SEQUENCE";
    case CMD_ERR_REFUSED:  return "REFUSED";
    default:               return "UNKNOWN";
    }
}