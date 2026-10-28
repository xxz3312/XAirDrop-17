/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef WONDER_FEEDBACK_STATE_H
#define WONDER_FEEDBACK_STATE_H
/* Caller serializes all operations. No packet is freed by this metadata core. */
#define WONDER_FB_SLOTS 64
#define WONDER_FB_TTL_MS 15000ULL
#define WONDER_FB_LEASE_MS 30000ULL
struct wonder_fb_slot {
    void *packet;
    unsigned long long token,expires;
    int delivered;
};
struct wonder_fb_state {
    struct wonder_fb_slot slots[WONDER_FB_SLOTS];
    unsigned long long owner,next_token,last_seen;
    int running,closing;
};
static inline int wonder_fb_claim(struct wonder_fb_state *s,unsigned long long owner,
                                  unsigned long long now)
{
    if (!owner || !s->running || s->closing || (s->owner && s->owner!=owner)) return 0;
    s->owner=owner;s->last_seen=now;return 1;
}
static inline int wonder_fb_offer(struct wonder_fb_state *s,void *packet,
                                  unsigned long long now)
{
    int i;
    if (!s->running || s->closing || !s->owner || !s->next_token) return 0;
    for (i=0;i<WONDER_FB_SLOTS;i++) if (!s->slots[i].packet) {
        s->slots[i]=(struct wonder_fb_slot){packet,s->next_token++,now+WONDER_FB_TTL_MS,0};
        return 1;
    }
    return 0;
}
static inline struct wonder_fb_slot *wonder_fb_take(struct wonder_fb_state *s)
{
    struct wonder_fb_slot *next=0;int i;
    for (i=0;i<WONDER_FB_SLOTS;i++) {
        struct wonder_fb_slot *p=&s->slots[i];
        if (p->packet && !p->delivered && (!next || p->token<next->token)) next=p;
    }
    return next;
}
static inline void *wonder_fb_remove(struct wonder_fb_slot *p)
{
    void *packet=p->packet;p->packet=0;p->delivered=0;return packet;
}
static inline void *wonder_fb_finish(struct wonder_fb_state *s,unsigned long long owner,
                                     unsigned long long token)
{
    int i;
    if (!owner || s->owner!=owner || !token) return 0;
    for (i=0;i<WONDER_FB_SLOTS;i++)
        if (s->slots[i].packet && s->slots[i].delivered && s->slots[i].token==token)
            return wonder_fb_remove(&s->slots[i]);
    return 0;
}
static inline int wonder_fb_sweep(struct wonder_fb_state *s,unsigned long long now,void **packets)
{
    int i,n=0;
    if (s->owner && now-s->last_seen>=WONDER_FB_LEASE_MS) s->owner=0;
    for (i=0;i<WONDER_FB_SLOTS;i++) {
        struct wonder_fb_slot *p=&s->slots[i];
        if (p->packet && (!s->running || !s->owner || now>=p->expires))
            packets[n++]=wonder_fb_remove(p);
    }
    return n;
}
#endif
