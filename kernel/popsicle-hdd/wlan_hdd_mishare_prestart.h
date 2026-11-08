/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef WLAN_HDD_MISHARE_PRESTART_H
#define WLAN_HDD_MISHARE_PRESTART_H
#include "wlan_hdd_mishare_session.h"
#include "wlan_hdd_mishare_rate.h"

/* Fresh caller-owned state, serialized with the same session/runtime owner.
 * Native parents must remain retained across polls. Zero means the fixed-rate
 * submissions completed, NOT firmware ACK, radio UP or public init readiness.
 */
struct mishare_prestart {
    bool selected, posted;
    u32 freq;
    u8 nss_2g, nss_5g;
    struct mishare_runtime_rate_request rate;
};

static inline bool
mishare_prestart_rate_equal(const struct mishare_runtime_rate_request *a,
                            const struct mishare_runtime_rate_request *b)
{
    return a->preamble == b->preamble && a->bw == b->bw && a->gi == b->gi &&
           a->nss == b->nss && a->mcs == b->mcs;
}

static inline int
mishare_prestart_step(struct mishare_prestart *c, struct mishare_session *session,
                      struct mishare_runtime_owner *owner, u32 freq,
                      u8 nss_2g, u8 nss_5g,
                      const struct wondertap_fixed_tx_rate_params *params)
{
    struct mishare_runtime_status s;
    struct mishare_runtime_rate_request rate;
    const struct mishare_runtime_rate_status *r = &s.rate;
    int ret;

    if (!c || !session || !owner || !freq || !nss_2g || nss_2g > 2 ||
        !nss_5g || nss_5g > 2 || !params)
        return -EINVAL;
    if (session->closing)
        return -ESHUTDOWN;
    if (session->error)
        return session->error;
    ret = mishare_rate_check(params);
    if (ret)
        return ret;
    if (params->nss > (freq < 3000 ? nss_2g : nss_5g))
        return -EOPNOTSUPP; /* Frequency/regulatory authority remains native. */
    rate.preamble = params->preamble;
    rate.bw = params->bw;
    rate.gi = params->gi;
    rate.nss = params->nss;
    rate.mcs = params->mcs;
    if (c->selected && (c->freq != freq || c->nss_2g != nss_2g ||
        c->nss_5g != nss_5g || !mishare_prestart_rate_equal(&c->rate, &rate)))
        return -EBUSY;
    if (!c->selected && (session->configured || session->stage != MISHARE_SESSION_NEW))
        return -EBUSY; /* Never adopt an ordinary/partly progressed session. */
    ret = mishare_runtime_snapshot(owner, &s);
    if (ret)
        return mishare_session_fail(session, ret);
    if (s.quiesced || s.draining || s.freed)
        return mishare_session_fail(session, -ESHUTDOWN);
    if (s.blocked || s.ndi.blocked || s.work_error || s.create_error ||
        s.ndi.create_error || s.ndi.context_error || s.ndi.completion_error ||
        s.ndi.pe_error || s.ndi.channel_error || s.ndi.start_plan_error ||
        s.radio.error || r->integrity_error)
        return mishare_session_fail(session, -EUCLEAN);
    if (s.ndi.start_plan_requested || s.ndi.radio_requested ||
        session->stage > MISHARE_SESSION_PLAN)
        return mishare_session_fail(session, -EBUSY);
    if (!c->selected) {
        if (r->requested)
            return mishare_session_fail(session, -EBUSY);
        c->selected = true; /* Before the first native call; no replay. */
        c->freq = freq;
        c->nss_2g = nss_2g;
        c->nss_5g = nss_5g;
        c->rate = rate;
    }
    if (session->stage < MISHARE_SESSION_PLAN) {
        if (r->requested)
            return mishare_session_fail(session, -EBUSY);
        return mishare_session_step(session, owner, freq, nss_2g, nss_5g);
    }
    if (!s.ndi.channel_completed)
        return -EINPROGRESS;
    if (!s.ndi.channel_submitted || !s.ndi.channel_prepared || s.ndi.channel_freq != freq)
        return mishare_session_fail(session, -EUCLEAN);
    if (!c->posted) {
        if (r->requested)
            return mishare_session_fail(session, -EBUSY);
        if (s.work_users || s.work_pending)
            return -EINPROGRESS; /* Channel completion precedes work_put. */
        c->posted = true; /* Completion may run inline in configure(). */
        ret = mishare_runtime_rate_configure(owner, params);
        if (ret != -EINPROGRESS)
            return mishare_session_fail(session, ret ? ret : -EUCLEAN);
        return -EINPROGRESS; /* Submit return is separate from completion. */
    }
    if (!r->requested || !mishare_prestart_rate_equal(&r->request, &c->rate))
        return mishare_session_fail(session, -EUCLEAN);
    if (!r->posted || !r->completed)
        return -EINPROGRESS;
    if (r->receipt.result)
        return mishare_session_fail(session, r->receipt.result);
    if (!r->accepted || !r->receipt.attempted || !r->receipt.complete ||
        r->receipt.busy || r->receipt.first_error || r->receipt.attempted_mask != 7 ||
        r->receipt.submitted_mask != 7)
        return mishare_session_fail(session, -EUCLEAN);
    if (s.work_pending || s.work_users)
        return -EINPROGRESS; /* Completion publishes while its reservation lives. */
    return 0; /* Remain in PLAN; never request START-plan or radio START. */
}
#endif
