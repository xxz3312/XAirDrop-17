// SPDX-License-Identifier: GPL-2.0-only
#include <assert.h>
#include <limits.h>
#include <stdio.h>
#include <string.h>
#include "../kernel/wonder/feedback_protocol.h"
#include "../kernel/wonder/feedback_state.h"
int main(void)
{
    struct wonder_fb_state s={.next_token=100};
    int packets[WONDER_FB_SLOTS+1];void *released[WONDER_FB_SLOTS];
    assert(!wonder_fb_claim(&s,1,0));
    s.running=1;assert(!wonder_fb_offer(&s,&packets[0],0));
    assert(wonder_fb_claim(&s,1,0));assert(!wonder_fb_claim(&s,2,0));
    assert(wonder_fb_offer(&s,&packets[0],0));
    assert(!wonder_fb_finish(&s,1,100)); /* not delivered */
    struct wonder_fb_slot *slot=wonder_fb_take(&s);
    assert(slot && slot->token==100 && slot->packet==&packets[0]);slot->delivered=1;
    assert(!wonder_fb_take(&s));
    assert(!wonder_fb_finish(&s,2,100));assert(!wonder_fb_finish(&s,1,99));
    assert(wonder_fb_finish(&s,1,100)==&packets[0]);assert(!wonder_fb_finish(&s,1,100));
    for (int i=0;i<WONDER_FB_SLOTS;i++) assert(wonder_fb_offer(&s,&packets[i],1));
    assert(!wonder_fb_offer(&s,&packets[WONDER_FB_SLOTS],1));
    for (int i=0;i<WONDER_FB_SLOTS;i++) {
        slot=wonder_fb_take(&s);assert(slot && slot->token==101U+(unsigned)i);slot->delivered=1;
    }
    assert(!wonder_fb_take(&s));
    assert(!wonder_fb_sweep(&s,WONDER_FB_TTL_MS,released));
    assert(wonder_fb_sweep(&s,1+WONDER_FB_TTL_MS,released)==WONDER_FB_SLOTS);
    for (int i=0;i<WONDER_FB_SLOTS;i++) assert(released[i]==&packets[i]);
    assert(!wonder_fb_finish(&s,1,101)); /* expired, late/duplicate completion */
    assert(wonder_fb_offer(&s,&packets[0],20000));
    assert(wonder_fb_claim(&s,1,20000));
    s.owner=0;assert(wonder_fb_sweep(&s,20000,released)==1 && released[0]==&packets[0]);
    assert(wonder_fb_claim(&s,2,20001));assert(wonder_fb_offer(&s,&packets[1],20001));
    slot=wonder_fb_take(&s);assert(slot);slot->delivered=1;unsigned long long token=slot->token;
    assert(!wonder_fb_finish(&s,1,token));
    assert(wonder_fb_sweep(&s,20001+WONDER_FB_LEASE_MS,released)==1 && !s.owner);
    assert(!wonder_fb_finish(&s,2,token));
    assert(wonder_fb_claim(&s,3,60000));assert(wonder_fb_offer(&s,&packets[0],60000));
    s.running=0;assert(wonder_fb_sweep(&s,60001,released)==1);
    s.closing=1;s.running=1;assert(!wonder_fb_claim(&s,3,60002));assert(!wonder_fb_offer(&s,&packets[0],60002));
    memset(&s,0,sizeof(s));s.running=1;s.owner=1;s.next_token=ULLONG_MAX;
    assert(wonder_fb_offer(&s,&packets[0],0));assert(!s.next_token);
    assert(!wonder_fb_offer(&s,&packets[1],0)); /* never reuse wrapped token */
    for (unsigned outcome=0;outcome<=2;outcome++) for (int noack=0;noack<2;noack++) for (int group=0;group<2;group++) {
        unsigned result=wonder_fb_evidence(outcome,noack,group);
        if (result==WONDER_FB_ACKED) assert(outcome==WONDER_FB_ACKED && !noack && !group);
        if (outcome==WONDER_FB_NOACK && !noack && !group) assert(result==WONDER_FB_FAILED);
        if (!outcome) assert(result==WONDER_FB_FAILED);
        if ((noack || group) && outcome) assert(result==WONDER_FB_NOACK);
    }
    puts("WONDER_FEEDBACK_OWNERSHIP_MODEL_PASS_ONLY");return 0;
}
