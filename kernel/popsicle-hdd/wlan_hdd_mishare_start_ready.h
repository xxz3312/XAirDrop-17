/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef WLAN_HDD_MISHARE_START_READY_H
#define WLAN_HDD_MISHARE_START_READY_H
#include "wlan_hdd_mishare_prestart.h"
#include "wlan_hdd_mishare_init.h"

/* One coherent runtime snapshot, no mutation or native submission. Zero is a
 * current pre-START configuration observation, NOT permission to remove the
 * runtime START guards, a reusable lease, firmware ACK or public init success.
 */
static inline int
mishare_start_ready_check(const struct mishare_runtime_status *s,
                          const struct mishare_prestart *c,
                          const struct mishare_session *session,
                          const struct mishare_init_request *request,
                          u8 nss_2g, u8 nss_5g)
{
    struct mishare_init_request canonical;
    struct mishare_runtime_rate_request expected;
    const struct mishare_runtime_rate_status *rate;
    const struct mishare_runtime_retry_status *retry;
    const struct mishare_ndi_status *n;
    const struct wondertap_init_params *p;
    int ret;

    if (!s || !c || !session || !request || !nss_2g || nss_2g > 2 ||
        !nss_5g || nss_5g > 2)
        return -EINVAL;
    ret = mishare_init_parse(&request->params, &canonical);
    if (ret)
        return ret;
    p = &canonical.params;
    ret = mishare_init_aggregation_check(&canonical);
    if (!ret)
        ret = mishare_rate_check(&p->tx_rate);
    if (ret)
        return ret;
    if (p->channel.bandwidth != WONDERTAP_RATE_BW_20 || p->rate_adaptation_enable ||
        p->tx_rate.nss > (p->channel.freq < 3000 ? nss_2g : nss_5g))
        return -EOPNOTSUPP;
    if (session->closing || s->quiesced || s->draining || s->freed)
        return -ESHUTDOWN;
    if (session->error)
        return session->error;
    rate = &s->rate;
    retry = &s->retry;
    n = &s->ndi;
    if (s->blocked || n->blocked || s->work_error || s->create_error ||
        s->reclaim_error || s->recovery_error || n->create_error || n->context_error ||
        n->completion_error || n->pe_error || n->channel_error || n->start_plan_error ||
        s->radio.error || rate->integrity_error || retry->integrity_error)
        return -EUCLEAN;
    if (session->stage > MISHARE_SESSION_PLAN || n->start_plan_requested ||
        n->start_plan_submitted || n->start_plan_completed || n->start_plan_ready ||
        n->radio_requested || s->radio.phase != MISHARE_RADIO_NEW ||
        s->radio.host_up || s->radio.closing || s->host_delete_accepted ||
        s->host_reclaim || s->mc_stop_seen || s->mc_drained ||
        s->recovery_window || s->recovery_window_closed ||
        s->ndi_reclaim_started || s->ndi_reclaim_ready || n->pe_delete_requested || n->peer_delete_pending ||
        n->delete_pending || n->dp_detaching || n->dp_freed ||
        rate->ordinary_admitted || rate->ordinary_completed ||
        rate->late_peer_armed || rate->late_peer_reply ||
        rate->late_delete_armed || rate->late_delete_reply || rate->peer_reset_armed ||
        rate->peer_reset_admitted || rate->peer_reset_completed || rate->tail_dp_attempted ||
        rate->tail_attempted || rate->tail_completed || rate->reset_admitted || rate->reset_completed)
        return -EBUSY;
    expected.preamble = p->tx_rate.preamble;
    expected.bw = p->tx_rate.bw;
    expected.gi = p->tx_rate.gi;
    expected.nss = p->tx_rate.nss;
    expected.mcs = p->tx_rate.mcs;
    if (c->selected && (c->freq != p->channel.freq || c->nss_2g != nss_2g ||
        c->nss_5g != nss_5g || !mishare_prestart_rate_equal(&c->rate, &expected)))
        return -EUCLEAN;
    if (session->configured && (session->freq != p->channel.freq ||
        session->nss_2g != nss_2g || session->nss_5g != nss_5g))
        return -EUCLEAN;
    if (s->bssid.error)
        return s->bssid.error;
    if (s->bssid.applied && (!s->bssid.requested ||
        memcmp(s->bssid.value, p->bssid, ETH_ALEN)))
        return -EUCLEAN;
    if (rate->requested && !mishare_prestart_rate_equal(&rate->request, &expected))
        return -EUCLEAN;
    if (retry->requested && (retry->data_limit != p->data_retry_limit ||
        retry->mgmt_limit != p->mgmt_retry_limit))
        return -EUCLEAN;
    if (rate->completed && rate->receipt.result)
        return rate->receipt.result;
    if (retry->completed && retry->result)
        return retry->result;
    if (!s->allocated || !c->selected || !c->posted || !session->configured ||
        session->stage != MISHARE_SESSION_PLAN || !s->bssid.requested || !s->bssid.applied ||
        !n->active || !n->create.wire_attempted || !n->create.wire_accepted ||
        !n->create.dp_attempted || !n->create.dp_attached ||
        !n->create.timer_ready || !n->legacy_ready || !n->wma_bound || !n->peer_created ||
        !n->pe_requested || !n->pe_submitted || !n->pe_completed || !n->pe_ready ||
        !n->channel_requested || !n->channel_submitted || !n->channel_completed || !n->channel_prepared ||
        !rate->requested || !rate->posted || !rate->completed ||
        !retry->requested || !retry->posted || !retry->completed)
        return -EINPROGRESS;
    if (n->channel_freq != p->channel.freq || !rate->accepted ||
        !rate->receipt.attempted || !rate->receipt.complete || rate->receipt.busy ||
        rate->receipt.first_error || rate->receipt.attempted_mask != 7 ||
        rate->receipt.submitted_mask != 7 || !retry->accepted ||
        !retry->receipt.attempted || !retry->receipt.complete ||
        !mishare_runtime_retry_receipt_valid(retry, &retry->receipt, 0, retry->vdev_id))
        return -EUCLEAN;
    if (s->work_pending || s->work_users)
        return -EINPROGRESS;
    return 0;
}
#endif
