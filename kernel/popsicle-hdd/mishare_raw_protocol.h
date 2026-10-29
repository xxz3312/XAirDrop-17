/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef MISHARE_RAW_PROTOCOL_H
#define MISHARE_RAW_PROTOCOL_H
/* Experimental private protocol. Words are little endian; byte access avoids
 * alignment assumptions in vendor data and captured frames. Includer: size_t. */
#define MISHARE_RAW_VENDOR_ID 0x001a11U
#define MISHARE_RAW_SUBCMD 0x1701U
#define MISHARE_RAW_VERSION 1U
#define MISHARE_RAW_HEADER 16U
#define MISHARE_RAW_MAX 2304U
#define MISHARE_RAW_ACTION_KIND 1U
/* Separate opt-in request kind: unprotected vendor-specific Action only. */
static inline int mishare_action_frame_valid(const unsigned char *p, size_t n)
{
    unsigned int fc;
    if (!p || n < 28 || n > MISHARE_RAW_MAX)
        return 0;
    fc = (unsigned int)p[0] | (unsigned int)p[1]<<8;
    return (fc & 0x00ff) == 0x00d0 &&
           !(fc & (0x0300 | 0x0400 | 0x4000 | 0x8000)) &&
           !(p[22] & 15) && p[24] == 127;
}
static inline unsigned int mishare_raw_word(const unsigned char *p)
{
    return (unsigned int)p[0] | (unsigned int)p[1]<<8 |
           (unsigned int)p[2]<<16 | (unsigned int)p[3]<<24;
}
static inline void mishare_raw_set_word(unsigned char *p, unsigned int n)
{
    p[0]=n;p[1]=n>>8;p[2]=n>>16;p[3]=n>>24;
}
static inline int mishare_raw_frame_valid(const unsigned char *p, size_t n)
{
    unsigned int fc, header;
    if (!p || n < 24 || n > MISHARE_RAW_MAX)
        return 0;
    fc = (unsigned int)p[0] | (unsigned int)p[1]<<8;
    /* Data or QoS Data, DS=0 or ToDS only, no protected/fragmented/HTC frame. */
    if ((p[0] != 0x08 && p[0] != 0x88) ||
        (fc & (0x0200 | 0x0400 | 0x4000 | 0x8000)) || (p[22] & 15))
        return 0;
    header = p[0] == 0x88 ? 26 : 24;
    if (n < header + 8)
        return 0;
    /* No A-MSDU or alternate ACK policy in this first path. */
    if (header == 26 && ((p[24] & 0xf8) || p[25]))
        return 0;
    return 1;
}
#endif
