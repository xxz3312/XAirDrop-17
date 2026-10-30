/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef WLAN_HDD_MISHARE_SESSION_H
#define WLAN_HDD_MISHARE_SESSION_H
#include <linux/errno.h>
#include "wlan_hdd_mishare_runtime.h"

/* Caller-owned progression, under the runtime owner's serialization/parent
 * contract. One native submission per call; never wait under RTNL/psoc sync.
 * No module parameter or default runtime entry enables this controller.
 */
enum mishare_session_stage {
    MISHARE_SESSION_NEW,
    MISHARE_SESSION_PREPARE,
    MISHARE_SESSION_PE,
    MISHARE_SESSION_CHANNEL,
    MISHARE_SESSION_PLAN,
    MISHARE_SESSION_START,
    MISHARE_SESSION_UP,
};
struct mishare_session {
    enum mishare_session_stage stage;
    u32 freq;
    u8 nss_2g, nss_5g;
    bool configured;
    bool closing;
    int error;
};

static inline int
mishare_session_fail(struct mishare_session *session, int error)
{
    if (!session->error)
        session->error = error ? error : -EUCLEAN;
    return session->error;
}

static inline int
mishare_session_step(struct mishare_session *session,
                     struct mishare_runtime_owner *owner,
                     u32 freq, u8 nss_2g, u8 nss_5g)
{
    struct mishare_runtime_status s;
    struct mishare_ndi_status *n = &s.ndi;
    int ret;

    if (!session || !owner || !freq || !nss_2g || nss_2g > 2 ||
        !nss_5g || nss_5g > 2)
        return -EINVAL;
    if (session->closing)
        return -ESHUTDOWN;
    if (session->error)
        return session->error;
    if (session->configured &&
        (session->freq != freq || session->nss_2g != nss_2g ||
         session->nss_5g != nss_5g))
        return -EBUSY;
    ret = mishare_runtime_snapshot(owner, &s);
    if (ret)
        return mishare_session_fail(session, ret);
    if (s.quiesced || s.draining || s.freed)
        return mishare_session_fail(session, -ESHUTDOWN);
    if (s.blocked || n->blocked || s.work_error || s.create_error ||
        n->create_error || n->context_error || n->completion_error ||
        n->pe_error || n->channel_error || n->start_plan_error ||
        s.radio.error)
        return mishare_session_fail(session, -EUCLEAN);
    if (!session->configured) {
        /* Do not adopt a partly started session owned by another caller. */
        if (n->active || n->create.wire_attempted || n->pe_requested ||
            n->channel_requested || n->start_plan_requested || n->radio_requested)
            return mishare_session_fail(session, -EBUSY);
        session->configured = true;
        session->freq = freq;
        session->nss_2g = nss_2g;
        session->nss_5g = nss_5g;
    }
    switch (session->stage) {
    case MISHARE_SESSION_NEW:
        /* Mark before submission, including synchronous failure. No retry. */
        session->stage = MISHARE_SESSION_PREPARE;
        ret = mishare_runtime_ndi_create(owner, nss_2g, nss_5g);
        break;
    case MISHARE_SESSION_PREPARE:
        if (!n->active || !n->create.wire_accepted || !n->create.dp_attached)
            return mishare_session_fail(session, -EUCLEAN);
        session->stage = MISHARE_SESSION_PE;
        ret = mishare_runtime_ndi_prepare(owner);
        break;
    case MISHARE_SESSION_PE:
        if (!n->legacy_ready || !n->wma_bound || !n->peer_created)
            return mishare_session_fail(session, -EUCLEAN);
        session->stage = MISHARE_SESSION_CHANNEL;
        ret = mishare_runtime_ndi_session(owner);
        break;
    case MISHARE_SESSION_CHANNEL:
        if (!n->pe_completed)
            return -EINPROGRESS;
        if (!n->pe_submitted || !n->pe_ready)
            return mishare_session_fail(session, -EUCLEAN);
        session->stage = MISHARE_SESSION_PLAN;
        ret = mishare_runtime_ndi_channel(owner, freq);
        break;
    case MISHARE_SESSION_PLAN:
        if (!n->channel_completed)
            return -EINPROGRESS;
        if (!n->channel_submitted || !n->channel_prepared || n->channel_freq != freq)
            return mishare_session_fail(session, -EUCLEAN);
        session->stage = MISHARE_SESSION_START;
        ret = mishare_runtime_ndi_start_plan(owner);
        break;
    case MISHARE_SESSION_START:
        if (!n->start_plan_completed)
            return -EINPROGRESS;
        if (!n->start_plan_submitted || !n->start_plan_ready ||
            n->start_plan.freq != freq)
            return mishare_session_fail(session, -EUCLEAN);
        session->stage = MISHARE_SESSION_UP;
        ret = mishare_runtime_ndi_start(owner);
        break;
    case MISHARE_SESSION_UP:
        if (s.radio.phase == MISHARE_RADIO_UP && s.radio.host_up &&
            n->radio_requested && !s.radio.closing)
            return 0;
        if (s.radio.phase == MISHARE_RADIO_NEW ||
            s.radio.phase == MISHARE_RADIO_STARTING ||
            s.radio.phase == MISHARE_RADIO_WAIT_START)
            return -EINPROGRESS;
        return mishare_session_fail(session, -EUCLEAN);
    default:
        return mishare_session_fail(session, -EUCLEAN);
    }
    if (ret && ret != -EINPROGRESS)
        return mishare_session_fail(session, ret);
    return -EINPROGRESS; /* Submission acceptance never reports radio UP. */
}
#endif
