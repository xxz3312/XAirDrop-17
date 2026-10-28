/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef WONDER_FEEDBACK_PROTOCOL_H
#define WONDER_FEEDBACK_PROTOCOL_H
#define WONDER_FB_VENDOR 0x001a11U
#define WONDER_FB_PULL 0x1702U
#define WONDER_FB_COMPLETE 0x1703U
#define WONDER_FB_RELEASE 0x1704U
#define WONDER_FB_VERSION 1U
#define WONDER_FB_HEADER 32U
#define WONDER_FB_MAX 2304U
#define WONDER_FB_FAILED 0U
#define WONDER_FB_NOACK 1U
#define WONDER_FB_ACKED 2U
static inline unsigned int wonder_fb_evidence(unsigned int outcome,int noack,int group)
{
    if (outcome==WONDER_FB_ACKED && !noack && !group) return WONDER_FB_ACKED;
    if (outcome!=WONDER_FB_FAILED && (noack || group)) return WONDER_FB_NOACK;
    return WONDER_FB_FAILED;
}
/* LE words: version, frame length, owner low/high, token low/high,
 * outcome, reserved. Requests without a frame have length zero. */
static inline unsigned int wonder_fb_word(const unsigned char *p)
{
    return (unsigned int)p[0] | (unsigned int)p[1]<<8 |
           (unsigned int)p[2]<<16 | (unsigned int)p[3]<<24;
}
static inline void wonder_fb_put(unsigned char *p, unsigned int n)
{
    p[0]=n;p[1]=n>>8;p[2]=n>>16;p[3]=n>>24;
}
#endif
