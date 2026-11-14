// SPDX-License-Identifier: GPL-2.0-only
/* Referenced host vdev ownership. Dormant until called by the DOWN host API. */
#include <linux/errno.h>
#include <linux/etherdevice.h>
#include <linux/slab.h>
#include <linux/module.h>
#include <linux/spinlock.h>
#include <wlan_objmgr_pdev_obj.h>
#include <wlan_objmgr_vdev_obj.h>
#include <wlan_vdev_mlme.h>
#include <wlan_osif_priv.h>
#include "wlan_hdd_mishare_events.h"
#include "wlan_hdd_mishare_runtime.h"
#include <qdf_status.h>

struct mishare_runtime_owner {
    struct mishare_runtime_owner *next;
    struct wlan_objmgr_psoc *psoc;
    struct wlan_objmgr_vdev *vdev;
    struct mishare_event_owner *events;
    struct mishare_radio *radio;
    unsigned long cookie;
    unsigned long pe_cookie;
    u8 mac[ETH_ALEN];
    bool referenced;
    struct mishare_runtime_status state;
};
static DEFINE_SPINLOCK(mishare_runtime_lock);
static struct mishare_runtime_owner *mishare_runtime_owners;
static int mishare_runtime_ndi_drain(struct mishare_runtime_owner *entry);
static void mishare_runtime_ndi_dp_freed(void *context);

/* MISHARE_RUNTIME_RATE_BEGIN */
/* A zero-attempt retry receipt adds no WMI setting to the already-qualified
 * rate-only prepared reset. This is eligibility, never a recovery window.
 * Keep attempted, pending, malformed and non-SSR origins quarantined.
 */
static bool mishare_runtime_retry_zero_attempt_ssr(struct mishare_runtime_owner *entry)
{
    const struct mishare_runtime_retry_status *r = &entry->state.retry;
    return r->requested && r->posted && r->completed && !r->integrity_error &&
           entry->state.quiesced == MISHARE_QUIESCE_SSR &&
           !entry->state.work_pending && !entry->state.work_users &&
           !entry->state.work_error && r->result < 0 && !r->receipt.attempted &&
           mishare_runtime_retry_receipt_valid(r, &r->receipt, r->result, 0);
}

/* Submitted retry settings belong to this never-STARTed VDEV, and are
 * discarded by the existing qualified prepared reset. Do not adopt ordinary
 * cleanup/peer/tail origins. Metadata only: safe after final native free too.
 */
static bool mishare_runtime_retry_prepared_ssr(struct mishare_runtime_owner *entry)
{
    const struct mishare_runtime_retry_status *r = &entry->state.retry;
    const struct mishare_runtime_rate_status *rate = &entry->state.rate;
    return r->requested && r->posted && r->accepted && r->completed &&
           !r->integrity_error && r->receipt.attempted &&
           entry->state.quiesced == MISHARE_QUIESCE_SSR && entry->state.mc_drained &&
           !entry->state.work_pending && !entry->state.work_users && !entry->state.work_error &&
           !entry->radio && !entry->state.ndi.radio_requested && (!entry->state.ndi.start_plan_requested || entry->state.start_preview.committed) &&
           !rate->ordinary_admitted && !rate->ordinary_completed &&
           !rate->late_peer_armed && !rate->late_peer_reply &&
           !rate->late_delete_armed && !rate->late_delete_reply &&
           !rate->peer_reset_armed && !rate->peer_reset_admitted && !rate->peer_reset_completed &&
           !rate->tail_dp_attempted && !rate->tail_attempted && !rate->tail_completed &&
           rate->requested && rate->posted && rate->accepted && rate->completed && !rate->integrity_error &&
           rate->receipt.attempted && rate->receipt.complete && !rate->receipt.busy &&
           !rate->receipt.result && !rate->receipt.first_error &&
           rate->receipt.attempted_mask == 7 && rate->receipt.submitted_mask == 7 &&
           mishare_runtime_retry_receipt_valid(r, &r->receipt, r->result, r->vdev_id);
}

/* Scalar-only receipt validation, valid after native VDEV storage is gone.
 * Existing MC reservations, native identity and cleanup qualification still
 * govern retirement. A preview never authorizes actual radio START. */
static bool mishare_preview_summary_empty(const struct mishare_ndi_start_summary *p)
{
    return !p->freq && !p->center_freq && !p->phy_mode && !p->tx_streams &&
           !p->rx_streams && !p->beacon_interval && !p->dtim_period;
}

/* Compare named scalars, not structure padding. Safe after native free. */
static bool mishare_preview_summary_equal(const struct mishare_ndi_start_summary *a,
                                          const struct mishare_ndi_start_summary *b)
{
    return a->freq == b->freq && a->center_freq == b->center_freq &&
           a->phy_mode == b->phy_mode && a->tx_streams == b->tx_streams &&
           a->rx_streams == b->rx_streams && a->beacon_interval == b->beacon_interval &&
           a->dtim_period == b->dtim_period;
}

static int mishare_runtime_preview_retire_check(struct mishare_runtime_owner *entry)
{
    const struct mishare_start_preview_status *p = &entry->state.start_preview;

    if (!p->requested)
        return p->posted || p->completed || p->integrity_error || p->committed || p->vdev_id || p->freq ||
               p->result || !mishare_preview_summary_empty(&p->summary) ? -EUCLEAN : 0;
    if (p->integrity_error || !p->freq || p->result > 0 ||
        !entry->state.rate.requested || !entry->state.retry.requested ||
        p->vdev_id != entry->state.retry.vdev_id)
        return -EUCLEAN;
    if (p->committed && (!p->posted || !p->completed || p->result ||
        !entry->state.ndi.start_plan_requested || !entry->state.ndi.start_plan_submitted ||
        !entry->state.ndi.start_plan_completed || !entry->state.ndi.start_plan_ready ||
        entry->state.ndi.start_plan_error ||
        !mishare_preview_summary_equal(&p->summary, &entry->state.ndi.start_plan)))
        return -EUCLEAN;
    if (!p->completed) {
        if (p->result || !mishare_preview_summary_empty(&p->summary))
            return -EUCLEAN;
        return -EINPROGRESS;
    }
    if (p->result) {
        if (!mishare_preview_summary_empty(&p->summary))
            return -EUCLEAN;
    } else if (p->summary.freq != p->freq ||
               p->summary.center_freq != p->freq || !p->summary.phy_mode ||
               !p->summary.tx_streams || p->summary.tx_streams > 2 ||
               p->summary.rx_streams != p->summary.tx_streams)
        return -EUCLEAN;
    if (entry->state.work_pending || entry->state.work_users)
        return -EINPROGRESS;
    if (!p->result && !p->posted)
        return -EUCLEAN;
    return 0;
}

static int mishare_runtime_rate_retire_check(struct mishare_runtime_owner *entry)
{
    const struct mishare_runtime_rate_status *r = &entry->state.rate;
    const struct mishare_runtime_retry_status *retry = &entry->state.retry;
    int preview_ret = mishare_runtime_preview_retire_check(entry);
    if (preview_ret)
        return preview_ret;
    if (retry->integrity_error || (!retry->requested &&
        (retry->posted || retry->accepted || retry->completed || retry->receipt.attempted)))
        return -EUCLEAN;
    if (retry->requested) {
        /* Fencing takes precedence over the ordinary pending-work wait. The
         * reservation still retains storage until completion returns. */
        if (entry->state.quiesced &&
            !mishare_runtime_retry_zero_attempt_ssr(entry) &&
            !mishare_runtime_retry_prepared_ssr(entry))
            return -EUCLEAN;
        if (!retry->posted || !retry->completed || entry->state.work_pending ||
            entry->state.work_users)
            return -EINPROGRESS;
        /* Separate zero-attempt and submitted prepared-SSR evidence. Ordinary
         * tail/peer-reset histories cannot inherit the latter permission. */
        if (!r->requested || (!retry->accepted && retry->receipt.attempted) ||
            !mishare_runtime_retry_receipt_valid(retry, &retry->receipt,
                                                  retry->result, retry->vdev_id))
            return -EUCLEAN;
    }
    if (r->integrity_error)
        return -EUCLEAN;
    if ((r->peer_reset_armed && (!r->ordinary_admitted || r->late_peer_armed)) ||
        (r->peer_reset_admitted && (!r->ordinary_admitted ||
         (!r->peer_reset_armed && !r->late_peer_reply))) ||
        (r->peer_timer_attempted && !r->peer_reset_admitted) ||
        (r->peer_timer_released && !r->peer_timer_attempted) ||
        (r->peer_dp_attempted && !r->peer_timer_released) ||
        (r->peer_finish_attempted && !r->peer_dp_attempted) ||
        (r->peer_reset_completed && !r->peer_finish_attempted) ||
        ((r->peer_reset_armed || r->peer_reset_admitted) &&
         (r->ordinary_completed || r->late_delete_armed || r->late_delete_reply ||
          r->tail_dp_attempted || r->tail_attempted ||
          r->tail_completed || r->reset_admitted || r->reset_completed)))
        return -EUCLEAN;
    if ((r->late_peer_reply && !r->late_peer_armed) ||
        ((r->late_peer_armed || r->late_peer_reply) && !r->ordinary_admitted) ||
        (r->late_peer_armed && r->late_delete_armed) ||
        (r->late_delete_reply && !r->late_delete_armed) ||
        ((r->late_delete_armed || r->late_delete_reply) && !r->ordinary_admitted) ||
        (r->tail_dp_attempted && !r->ordinary_admitted) ||
        (r->tail_completed && (!r->tail_attempted || !r->ordinary_completed)) ||
        ((r->tail_attempted || r->tail_completed) && !r->ordinary_admitted) ||
        (r->ordinary_completed && !r->ordinary_admitted) ||
        ((r->ordinary_admitted || r->ordinary_completed) &&
         (!r->requested || !r->posted || !r->accepted || !r->completed ||
          !r->receipt.attempted || r->reset_admitted || r->reset_completed)) ||
        (r->reset_completed && !r->reset_admitted) ||
        ((r->reset_admitted || r->reset_completed) &&
         (!r->requested || !r->posted || !r->accepted || !r->completed || !r->receipt.attempted)))
        return -EUCLEAN;
    if (!r->requested)
        return r->posted || r->accepted || r->completed || r->ordinary_admitted || r->ordinary_completed || r->reset_admitted ||
               r->reset_completed || r->receipt.attempted ||
               r->receipt.attempted_mask || r->receipt.submitted_mask || r->request.nss ? -EUCLEAN : 0;
    if (!r->posted || !r->completed)
        return -EINPROGRESS;
    /* Ordinary pre-configuration cleanup cannot qualify applied settings.
     * Prepared SSR uses its separate eligibility and native-window checks.
     */
    return r->receipt.attempted ? -EOPNOTSUPP : 0;
}

/* Pure completion evidence shared by ordinary and SSR-final bookkeeping.
 * No pointer below is dereferenced; all native release origins were observed.
 */
static bool mishare_runtime_rate_ordinary_terminal(struct mishare_runtime_owner *entry)
{
    const struct mishare_runtime_rate_status *r = &entry->state.rate;
    const struct mishare_ndi_status *n = &entry->state.ndi;
    return !(!r->ordinary_admitted || (r->tail_attempted && !r->tail_completed) || n->active || n->pe_ready || entry->pe_cookie ||
            !n->pe_delete_requested || !n->pe_delete_submitted || !n->pe_delete_completed ||
            !n->peer_delete_pending || !n->peer_delete_submitted || !n->peer_delete_replied ||
            !n->delete_pending || !n->delete_submitted || !n->delete_replied ||
            !n->dp_detaching || !n->dp_detach_submitted || !n->dp_freed ||
            n->create.timer_ready || n->create.stats_owned || n->legacy_ready || n->wma_bound);
}

/* Scalar-only configuration history, including after native resources free.
 * A success never replaces current parent/regulatory checks by the caller. */
static int mishare_runtime_configured_history(struct mishare_runtime_owner *e)
{
    const struct mishare_start_preview_status *p = &e->state.start_preview;
    const struct mishare_runtime_rate_status *r = &e->state.rate;
    const struct mishare_runtime_retry_status *retry = &e->state.retry;
    const struct mishare_ndi_status *n = &e->state.ndi;
    int ret = mishare_runtime_preview_retire_check(e);

    if (ret)
        return ret;
    if (!p->committed || !r->requested || !r->posted || !r->accepted || !r->completed ||
        r->integrity_error || !r->receipt.attempted || !r->receipt.complete || r->receipt.busy ||
        r->receipt.result || r->receipt.first_error || r->receipt.attempted_mask != 7 ||
        r->receipt.submitted_mask != 7 || !retry->requested || !retry->posted || !retry->accepted ||
        !retry->completed || retry->integrity_error || retry->result ||
        !mishare_runtime_retry_receipt_valid(retry, &retry->receipt, 0, p->vdev_id) ||
        !e->state.bssid.requested || !e->state.bssid.applied || e->state.bssid.error ||
        n->channel_freq != p->freq || n->radio_submit_error)
        return -EUCLEAN;
    return 0;
}

/* Ordinary DOWN only; never project BLOCKED/SSR into terminal success. */
static bool mishare_runtime_configured_down(struct mishare_runtime_owner *e)
{
    const struct mishare_configured_radio_status *c = &e->state.configured_radio;
    const struct mishare_radio_status *r = &e->state.radio;

    return c->requested && c->returned && c->start_result == -EINPROGRESS &&
           c->stop_requested && c->stopped && !c->stop_error && !e->radio &&
           e->state.ndi.radio_requested && !mishare_runtime_configured_history(e) &&
           !e->state.quiesced && r->phase == MISHARE_RADIO_DOWN && r->closing &&
           r->start_attempted && r->stop_attempted && r->host_up &&
           r->down_attempted && r->down_accepted && !r->pending && !r->users && !r->error &&
           !r->fence.recorded && r->fence.phase == MISHARE_RADIO_NEW &&
           !r->fence.error && !r->fence.closing && !r->fence.start_attempted &&
           !r->fence.stop_attempted && !r->fence.host_up && !r->fence.down_attempted &&
           !r->fence.down_accepted && !r->fence.pending && !r->fence.users &&
           !r->fence.start_sm_entered && !r->fence.start_sm_call_active &&
           !r->fence.start_reply_queued && !r->fence.stop_reply_queued &&
           !r->fence.applying_start_reply && !r->fence.applying_stop_reply &&
           !r->ssr_cancelled_before_start && !r->ssr_start_submit_error &&
           !r->ssr_start_callback_refused && !r->ssr_start_body_aborted &&
           !r->ssr_start_prepared_aborted && !r->ssr_start_sm_entry_aborted &&
           !r->ssr_start_init_rejected && !r->down_fence_callback_seen &&
           !r->down_retire_timer_attempted && !r->down_retire_timer_released &&
           !r->down_retired && !r->down_retire_error;
}

/* Registry lock held. Only normal pre-START DELETE may consume this policy.
 * Admission is not an ACK: existing PE/peer/VDEV/DP callbacks still gate every
 * step. Original configuration history is never rewritten during cleanup.
 */
static int mishare_runtime_rate_ordinary_check(struct mishare_runtime_owner *entry)
{
    const struct mishare_runtime_rate_status *r = &entry->state.rate;
    const struct mishare_ndi_status *n = &entry->state.ndi;
    int ret = mishare_runtime_rate_retire_check(entry);

    if (ret != -EOPNOTSUPP)
        return ret;
    if (entry->state.quiesced || r->reset_admitted || r->reset_completed ||
        entry->radio || (n->radio_requested && !mishare_runtime_configured_down(entry)) ||
        (entry->state.configured_radio.requested && !mishare_runtime_configured_down(entry)) ||
        (n->start_plan_requested && !entry->state.start_preview.committed) ||
        entry->state.ndi_reclaim_started || entry->state.host_reclaim ||
        entry->state.recovery_window || entry->state.recovery_window_closed)
        return -EOPNOTSUPP;
    if (!r->accepted || entry->state.blocked || n->blocked || n->completion_error ||
        entry->state.work_error || entry->state.reclaim_error || entry->state.recovery_error)
        return -EUCLEAN;
    if (entry->state.work_pending || entry->state.work_users)
        return -EINPROGRESS;
    if (r->ordinary_completed) {
        if (!mishare_runtime_rate_ordinary_terminal(entry))
            return -EUCLEAN;
    } else if (!r->ordinary_admitted &&
               (!entry->vdev || !entry->referenced || !entry->events ||
                entry->cookie != (unsigned long)entry->vdev || !entry->pe_cookie ||
                entry->state.draining || !n->active || !n->legacy_ready || !n->wma_bound ||
                !n->peer_created || !n->pe_submitted || !n->pe_completed || !n->pe_ready ||
                !n->channel_submitted || !n->channel_completed || !n->channel_prepared ||
                !n->create.timer_ready || !n->create.dp_attached ||
                n->pe_delete_requested || n->peer_delete_pending || n->delete_pending || n->dp_detaching))
        return -EOPNOTSUPP;
    return 0;
}

/* Registry lock held. This is eligibility, not the native recovery window.
 * Only cds_post_disable's HTC/HIF/WMI qualification may open that window.
 */
static int mishare_runtime_rate_reset_check(struct mishare_runtime_owner *entry)
{
    const struct mishare_runtime_rate_status *r = &entry->state.rate;
    const struct mishare_ndi_status *n = &entry->state.ndi;
    int ret = mishare_runtime_rate_retire_check(entry);

    if (ret != -EOPNOTSUPP)
        return ret;
    if (r->ordinary_admitted || r->ordinary_completed ||
        entry->state.quiesced != MISHARE_QUIESCE_SSR ||
        entry->radio || n->radio_requested || (n->start_plan_requested && !entry->state.start_preview.committed))
        return -EOPNOTSUPP;
    if (entry->state.work_error || entry->state.recovery_error ||
        entry->state.reclaim_error || n->completion_error)
        return -EUCLEAN;
    if (r->reset_completed) {
        if (!r->reset_admitted || !entry->state.ndi_reclaim_started ||
            !entry->state.ndi_reclaim_ready || !entry->state.recovery_timer_attempted ||
            !entry->state.recovery_timer_released || !entry->state.recovery_pe_attempted ||
            !entry->state.recovery_pe_released || !entry->state.recovery_context_attempted ||
            !entry->state.recovery_context_finish_attempted || !entry->state.recovery_context_released ||
            !entry->state.recovery_peer_released || !entry->state.recovery_dp_attempted ||
            !entry->state.recovery_dp_freed || n->active || n->legacy_ready || n->wma_bound ||
            n->peer_created || n->pe_ready || n->create.timer_ready || n->create.dp_attached)
            return -EUCLEAN;
    } else {
        if (entry->state.recovery_window_closed)
            return -ESHUTDOWN;
        if (r->reset_admitted) {
            if (!entry->state.recovery_window)
                return -EUCLEAN;
        } else if (!entry->vdev || !entry->referenced || !entry->events ||
                   !n->active || !n->legacy_ready || !n->wma_bound || !n->peer_created ||
                   !n->pe_submitted || !n->pe_completed || !n->pe_ready ||
                   !n->channel_submitted || !n->channel_completed || !n->channel_prepared)
            return -EOPNOTSUPP;
    }
    if (!entry->state.mc_drained || entry->state.work_pending || entry->state.work_users)
        return -EINPROGRESS;
    return 0;
}

/* Snapshot before the original SSR fence, for a real peer reply which has
 * already arrived. The late-peer path uses its own original-fence receipt. */
static bool mishare_runtime_rate_peer_ready(struct mishare_runtime_owner *entry)
{
    const struct mishare_runtime_rate_status *r = &entry->state.rate;
    const struct mishare_ndi_status *n = &entry->state.ndi;
    return mishare_runtime_rate_retire_check(entry) == -EOPNOTSUPP &&
           r->ordinary_admitted && !r->ordinary_completed && !r->tail_dp_attempted &&
           !r->tail_attempted && !r->tail_completed && !r->reset_admitted && !r->reset_completed &&
           !entry->radio && !n->radio_requested && !n->start_plan_requested &&
           !entry->state.work_error && !entry->state.recovery_error && !entry->state.reclaim_error &&
           !n->completion_error && !entry->state.host_reclaim && !entry->state.ndi_reclaim_started &&
           entry->state.allocated && !entry->state.freed && !entry->state.draining &&
           entry->vdev && entry->referenced && entry->events &&
           entry->cookie == (unsigned long)entry->vdev && !entry->pe_cookie &&
           n->active && n->legacy_ready && n->wma_bound && n->peer_created && !n->pe_ready &&
           n->pe_delete_requested && n->pe_delete_submitted && n->pe_delete_completed &&
           n->peer_delete_pending && n->peer_delete_submitted && n->peer_delete_replied &&
           !n->delete_pending && !n->delete_submitted && !n->delete_replied &&
           !n->dp_detaching && !n->dp_detach_submitted && !n->dp_freed &&
           n->create.timer_ready && n->create.dp_attempted && n->create.dp_attached &&
           n->create.dp_cookie && n->create.stats_owned;
}

/* No synthetic VDEV DELETE evidence. This route has its own completion
 * record, and can retire metadata after the native window is closed. */
static int mishare_runtime_rate_peer_reset_check(struct mishare_runtime_owner *entry)
{
    const struct mishare_runtime_rate_status *r = &entry->state.rate;
    const struct mishare_ndi_status *n = &entry->state.ndi;
    int ret = mishare_runtime_rate_retire_check(entry);
    if (ret != -EOPNOTSUPP)
        return ret;
    if ((!r->peer_reset_armed && !r->late_peer_reply) || !r->ordinary_admitted ||
        r->ordinary_completed || r->tail_dp_attempted || r->tail_attempted || r->tail_completed ||
        r->reset_admitted || r->reset_completed || entry->state.quiesced != MISHARE_QUIESCE_SSR ||
        entry->radio || n->radio_requested || n->start_plan_requested)
        return -EOPNOTSUPP;
    if (entry->state.work_error || entry->state.recovery_error || entry->state.reclaim_error ||
        n->completion_error || entry->state.ndi_reclaim_started || entry->state.host_reclaim)
        return -EUCLEAN;
    if (!n->pe_delete_requested || !n->pe_delete_submitted || !n->pe_delete_completed ||
        n->pe_ready || entry->pe_cookie || !n->peer_delete_pending ||
        !n->peer_delete_submitted || !n->peer_delete_replied ||
        n->delete_pending || n->delete_submitted || n->delete_replied)
        return -EOPNOTSUPP;
    if (!entry->state.mc_drained || entry->state.work_pending || entry->state.work_users)
        return -EINPROGRESS;
    if (r->peer_reset_completed) {
        if (!r->peer_reset_admitted || !r->peer_timer_released || !r->peer_dp_attempted ||
            !r->peer_finish_attempted || n->active || n->peer_created ||
            n->legacy_ready || n->wma_bound || n->create.timer_ready || n->create.stats_owned ||
            !n->dp_detaching || !n->dp_detach_submitted || !n->dp_freed)
            return -EUCLEAN;
        if (entry->state.host_delete_accepted)
            return entry->state.allocated && entry->state.draining && !entry->vdev &&
                   !entry->referenced && !entry->events ? 0 : -EUCLEAN;
    } else {
        if (entry->state.recovery_window_closed)
            return -ESHUTDOWN;
        if (r->peer_finish_attempted || (r->peer_timer_attempted && !r->peer_timer_released))
            return -EUCLEAN;
        if (!n->active || !n->legacy_ready || !n->wma_bound || !n->peer_created ||
            !n->create.dp_attempted || !n->create.dp_attached || !n->create.dp_cookie ||
            n->create.timer_ready == r->peer_timer_released)
            return -EOPNOTSUPP;
        if (r->peer_dp_attempted) {
            if (!n->dp_detaching || !n->dp_detach_submitted || n->create.stats_owned)
                return -EUCLEAN;
        } else if (n->dp_detaching || n->dp_detach_submitted || n->dp_freed || !n->create.stats_owned)
            return -EOPNOTSUPP;
    }
    return entry->vdev && entry->referenced && entry->events &&
           entry->cookie == (unsigned long)entry->vdev && entry->state.allocated &&
           !entry->state.draining && !entry->state.freed ? 0 : -EUCLEAN;
}

/* SSR handoff only AFTER normal native cleanup and accepted host deletion.
 * This never resumes PE/peer/VDEV/DP operations. The final API and batch still
 * require the original MC drain and actual final-free before freeing metadata.
 */
static int mishare_runtime_rate_final_check(struct mishare_runtime_owner *entry)
{
    const struct mishare_runtime_rate_status *r = &entry->state.rate;
    int ret;

    if (r->peer_reset_completed)
        return mishare_runtime_rate_peer_reset_check(entry);
    if (r->reset_completed)
        return mishare_runtime_rate_reset_check(entry);
    ret = mishare_runtime_rate_retire_check(entry);
    if (ret != -EOPNOTSUPP || !r->ordinary_completed)
        return ret;
    if (entry->state.quiesced != MISHARE_QUIESCE_SSR ||
        entry->radio || entry->state.ndi.radio_requested || entry->state.ndi.start_plan_requested)
        return -EOPNOTSUPP;
    if (!mishare_runtime_rate_ordinary_terminal(entry) ||
        !entry->state.host_delete_accepted || !entry->state.draining ||
        !entry->state.allocated || entry->vdev || entry->referenced || entry->events ||
        entry->state.work_error || entry->state.reclaim_error || entry->state.recovery_error ||
        entry->state.ndi.completion_error || entry->state.ndi_reclaim_started ||
        entry->state.host_reclaim)
        return -EUCLEAN;
    return 0;
}

/* Eligibility for an ordinary DELETE/DP tail; this never opens the native
 * recovery window. Ordinary DP completion remains its original callback.
 */
static int mishare_runtime_rate_tail_check(struct mishare_runtime_owner *entry)
{
    const struct mishare_runtime_rate_status *r = &entry->state.rate;
    const struct mishare_ndi_status *n = &entry->state.ndi;
    int ret = mishare_runtime_rate_retire_check(entry);

    if (ret != -EOPNOTSUPP)
        return ret;
    if (!r->ordinary_admitted || r->reset_admitted || r->reset_completed ||
        entry->state.quiesced != MISHARE_QUIESCE_SSR || entry->radio ||
        n->radio_requested || n->start_plan_requested)
        return -EOPNOTSUPP;
    if (entry->state.work_error || entry->state.recovery_error || entry->state.reclaim_error ||
        n->completion_error || entry->state.ndi_reclaim_started || entry->state.host_reclaim)
        return -EUCLEAN;
    if (!entry->state.mc_drained || entry->state.work_pending || entry->state.work_users)
        return -EINPROGRESS;
    if (r->tail_completed) {
        if (!mishare_runtime_rate_ordinary_terminal(entry))
            return -EUCLEAN;
        if (entry->state.host_delete_accepted)
            return mishare_runtime_rate_final_check(entry);
    } else {
        if (r->ordinary_completed)
            return -EOPNOTSUPP;
        if (r->tail_attempted)
            return -EUCLEAN;
        if (entry->state.recovery_window_closed)
            return -ESHUTDOWN;
        if (!n->active || !n->legacy_ready || !n->wma_bound || n->pe_ready || entry->pe_cookie ||
            !n->pe_delete_requested || !n->pe_delete_submitted || !n->pe_delete_completed ||
            !n->peer_delete_pending || !n->peer_delete_submitted || !n->peer_delete_replied ||
            !n->delete_pending || !n->delete_submitted || !n->delete_replied)
            return -EOPNOTSUPP;
        if (n->dp_detaching) {
            if (!n->dp_detach_submitted || n->create.timer_ready || n->create.stats_owned)
                return -EOPNOTSUPP;
        } else if (r->tail_dp_attempted || n->dp_detach_submitted || n->dp_freed ||
                   !n->create.dp_attempted || !n->create.dp_attached ||
                   !n->create.dp_cookie || !n->create.stats_owned)
            return -EOPNOTSUPP;
    }
    if (!entry->vdev || !entry->referenced || !entry->events ||
        entry->cookie != (unsigned long)entry->vdev || entry->state.draining ||
        !entry->state.allocated || entry->state.freed)
        return -EUCLEAN;
    return 0;
}

/* Pure snapshot shape, used before the first SSR fence and on the actual
 * native reply origin. No ACK, window or cleanup is manufactured here.
 */
static bool mishare_runtime_rate_delete_inflight(struct mishare_runtime_owner *entry)
{
    const struct mishare_runtime_rate_status *r = &entry->state.rate;
    const struct mishare_ndi_status *n = &entry->state.ndi;

    return mishare_runtime_rate_retire_check(entry) == -EOPNOTSUPP &&
           r->ordinary_admitted && !r->ordinary_completed && !r->tail_dp_attempted &&
           !r->tail_attempted && !r->tail_completed && !r->reset_admitted && !r->reset_completed &&
           !entry->radio && !n->radio_requested && !n->start_plan_requested &&
           !entry->state.work_error && !entry->state.recovery_error && !entry->state.reclaim_error &&
           !n->completion_error && !entry->state.host_reclaim && !entry->state.ndi_reclaim_started &&
           entry->state.allocated && !entry->state.freed && !entry->state.draining &&
           entry->vdev && entry->referenced && entry->events &&
           entry->cookie == (unsigned long)entry->vdev && !entry->pe_cookie &&
           n->active && n->legacy_ready && n->wma_bound && !n->pe_ready &&
           n->pe_delete_requested && n->pe_delete_submitted && n->pe_delete_completed &&
           n->peer_delete_pending && n->peer_delete_submitted && n->peer_delete_replied &&
           n->delete_pending && n->delete_submitted && !n->delete_replied &&
           !n->dp_detaching && !n->dp_detach_submitted && !n->dp_freed;
}

/* A native self-peer reply may be observed after the original SSR fence.
 * It grants no VDEV DELETE/DP or parent-release admission.
 */
static bool mishare_runtime_rate_peer_inflight(struct mishare_runtime_owner *entry)
{
    const struct mishare_runtime_rate_status *r = &entry->state.rate;
    const struct mishare_ndi_status *n = &entry->state.ndi;

    return mishare_runtime_rate_retire_check(entry) == -EOPNOTSUPP &&
           r->ordinary_admitted && !r->ordinary_completed && !r->tail_dp_attempted &&
           !r->tail_attempted && !r->tail_completed && !r->reset_admitted && !r->reset_completed &&
           !entry->radio && !n->radio_requested && !n->start_plan_requested &&
           !entry->state.work_error && !entry->state.recovery_error && !entry->state.reclaim_error &&
           !n->completion_error && !entry->state.host_reclaim && !entry->state.ndi_reclaim_started &&
           entry->state.allocated && !entry->state.freed && !entry->state.draining &&
           entry->vdev && entry->referenced && entry->events &&
           entry->cookie == (unsigned long)entry->vdev && !entry->pe_cookie &&
           n->active && n->legacy_ready && n->wma_bound && n->peer_created && !n->pe_ready &&
           n->pe_delete_requested && n->pe_delete_submitted && n->pe_delete_completed &&
           n->peer_delete_pending && n->peer_delete_submitted && !n->peer_delete_replied &&
           !n->delete_pending && !n->delete_submitted && !n->delete_replied &&
           !n->dp_detaching && !n->dp_detach_submitted && !n->dp_freed;
}

int mishare_runtime_rate_begin(struct mishare_runtime_owner *owner,
                               const struct mishare_runtime_rate_request *request,
                               struct wlan_objmgr_vdev **vdev)
{
    struct mishare_runtime_owner *entry;
    struct mishare_ndi_status *n;
    unsigned long flags;
    int ret = -ENOENT;
    if (!vdev)
        return -EINVAL;
    *vdev = NULL;
    if (!owner || !request || !request->nss || request->nss > 2)
        return -EINVAL;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    for (entry = mishare_runtime_owners; entry; entry = entry->next) {
        if (entry != owner)
            continue;
        n = &entry->state.ndi;
        if (entry->state.rate.integrity_error)
            ret = -EUCLEAN;
        else if (entry->state.rate.requested)
            ret = -EALREADY;
        else if (mishare_runtime_rate_retire_check(entry) ||
                 entry->state.blocked || n->blocked || n->completion_error)
            ret = -EUCLEAN;
        else if (entry->state.quiesced || entry->state.draining)
            ret = -ESHUTDOWN;
        else if (!entry->vdev || !entry->referenced || !entry->events || entry->radio ||
                 !entry->state.allocated || entry->state.freed || entry->state.work_pending ||
                 entry->state.work_users || !n->active || !n->legacy_ready || !n->wma_bound ||
                 !n->peer_created || !n->pe_ready || !n->pe_submitted || !n->pe_completed ||
                 !n->channel_submitted || !n->channel_completed || !n->channel_prepared ||
                 n->start_plan_requested || n->radio_requested || n->pe_delete_requested ||
                 n->peer_delete_pending || n->delete_pending)
            ret = -EBUSY;
        else {
            entry->state.rate.request = *request;
            entry->state.rate.requested = true;
            *vdev = entry->vdev;
            ret = 0;
        }
        break;
    }
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    return ret;
}

void mishare_runtime_rate_posted(struct mishare_runtime_owner *owner, int result)
{
    struct mishare_runtime_owner *entry;
    struct mishare_runtime_rate_status *r;
    unsigned long flags;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    for (entry = mishare_runtime_owners; entry; entry = entry->next) {
        if (entry != owner)
            continue;
        r = &entry->state.rate;
        if (!r->requested || r->posted || result > 0 || (result && r->completed)) {
            r->integrity_error = true;
        } else {
            r->posted = true;
            r->accepted = !result;
            if (result) {
                r->completed = true;
                r->receipt.result = result;
            }
        }
        break;
    }
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
}

void mishare_runtime_rate_complete(struct mishare_runtime_owner *owner,
                                    const struct mishare_runtime_rate_result *result)
{
    struct mishare_runtime_owner *entry;
    struct mishare_runtime_rate_status *r;
    unsigned long flags;
    if (!result)
        return;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    for (entry = mishare_runtime_owners; entry; entry = entry->next) {
        if (entry != owner)
            continue;
        r = &entry->state.rate;
        if (!r->requested || r->completed || (r->posted && !r->accepted) ||
            !entry->state.work_pending || entry->state.work_users || result->busy ||
            result->result > 0 || result->attempted != (result->attempted_mask != 0) ||
            (result->attempted_mask != 0 && result->attempted_mask != 1 &&
             result->attempted_mask != 3 && result->attempted_mask != 7) ||
            (result->submitted_mask & ~result->attempted_mask) ||
            (result->attempted && result->first_error != result->result) ||
            (!result->attempted && (result->first_error || !result->result)) ||
            (result->result ? (result->complete ||
                result->submitted_mask != (result->attempted_mask >> 1)) :
                (!result->complete || result->attempted_mask != 7 || result->submitted_mask != 7))) {
            r->integrity_error = true;
        } else {
            r->receipt = *result;
            r->completed = true;
        }
        break;
    }
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
}
/* MISHARE_RUNTIME_RATE_END */

/* MISHARE_RUNTIME_RETRY_BEGIN */
int mishare_runtime_retry_begin(struct mishare_runtime_owner *owner,
                    u8 data_limit, u8 mgmt_limit, struct wlan_objmgr_vdev **vdev)
{
    struct mishare_runtime_owner *entry;
    struct mishare_ndi_status *n;
    struct mishare_runtime_rate_status *r;
    unsigned long flags;
    int ret = -ENOENT;
    if (!vdev)
        return -EINVAL;
    *vdev = NULL;
    if (!owner)
        return -EINVAL;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    for (entry = mishare_runtime_owners; entry; entry = entry->next) {
        if (entry != owner)
            continue;
        n = &entry->state.ndi;
        r = &entry->state.rate;
        if (entry->state.retry.integrity_error || r->integrity_error ||
            entry->state.work_error || n->completion_error)
            ret = -EUCLEAN;
        else if (entry->state.retry.requested)
            ret = -EALREADY;
        else if (entry->state.quiesced || entry->state.draining || entry->state.freed)
            ret = -ESHUTDOWN;
        else if (entry->state.blocked || n->blocked)
            ret = -EUCLEAN;
        else if (!entry->vdev || !entry->referenced || !entry->events ||
                 entry->cookie != (unsigned long)entry->vdev || !entry->pe_cookie ||
                 !entry->state.allocated || entry->state.work_pending || entry->state.work_users ||
                 entry->radio || n->radio_requested || n->start_plan_requested ||
                 n->pe_delete_requested || n->peer_delete_pending || n->delete_pending ||
                 !n->active || !n->legacy_ready || !n->wma_bound || !n->peer_created ||
                 !n->pe_ready || !n->pe_submitted || !n->pe_completed ||
                 !n->channel_submitted || !n->channel_completed || !n->channel_prepared ||
                 !r->requested || !r->posted || !r->accepted || !r->completed ||
                 r->receipt.result || r->receipt.first_error || r->receipt.busy ||
                 !r->receipt.attempted || !r->receipt.complete ||
                 r->receipt.attempted_mask != 7 || r->receipt.submitted_mask != 7 ||
                 r->ordinary_admitted || r->reset_admitted)
            ret = -EBUSY;
        else {
            entry->state.retry.requested = true;
            entry->state.retry.data_limit = data_limit;
            entry->state.retry.mgmt_limit = mgmt_limit;
            entry->state.retry.vdev_id = wlan_vdev_get_id(entry->vdev);
            *vdev = entry->vdev;
            ret = 0;
        }
        break;
    }
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    return ret;
}

void mishare_runtime_retry_posted(struct mishare_runtime_owner *owner, int result)
{
    struct mishare_runtime_owner *entry;
    unsigned long flags;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    for (entry = mishare_runtime_owners; entry; entry = entry->next) {
        struct mishare_runtime_retry_status *r = &entry->state.retry;
        if (entry != owner)
            continue;
        if (!r->requested || r->posted || result > 0 || (result && r->completed))
            r->integrity_error = true;
        else {
            r->posted = true;
            r->accepted = !result;
            if (result) {
                r->completed = true;
                r->result = result;
            }
        }
        break;
    }
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
}

void mishare_runtime_retry_complete(struct mishare_runtime_owner *owner,
                     const struct mishare_retry_submission *receipt, int result)
{
    struct mishare_runtime_owner *entry;
    unsigned long flags;
    if (!receipt)
        return;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    for (entry = mishare_runtime_owners; entry; entry = entry->next) {
        struct mishare_runtime_retry_status *r = &entry->state.retry;
        if (entry != owner)
            continue;
        if (!r->requested || r->completed || (r->posted && !r->accepted) ||
            !entry->vdev || entry->state.retry.vdev_id != wlan_vdev_get_id(entry->vdev) ||
            !entry->state.work_pending || entry->state.work_users ||
            !mishare_runtime_retry_receipt_valid(r, receipt, result,
                                                 wlan_vdev_get_id(entry->vdev)))
            r->integrity_error = true;
        else {
            r->receipt = *receipt;
            r->result = result;
            r->completed = true;
        }
        break;
    }
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
}
/* MISHARE_RUNTIME_RETRY_END */


enum mishare_radio_cancel_origin { MISHARE_CANCEL_FLUSH, MISHARE_CANCEL_REFUSAL, MISHARE_CANCEL_BODY_ABORT, MISHARE_CANCEL_PREPARED_ABORT, MISHARE_CANCEL_SM_ENTRY_ABORT, MISHARE_CANCEL_INIT_REJECT };

static void mishare_runtime_radio_cancel_origin(struct wlan_objmgr_psoc *psoc,
                                                struct wlan_objmgr_vdev *vdev,
                                                void *owner, void *radio_token, enum mishare_radio_cancel_origin origin)
{
    struct mishare_runtime_owner *entry;
    unsigned long flags;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    for (entry = mishare_runtime_owners; entry; entry = entry->next) {
        if (entry != owner || entry->psoc != psoc || entry->vdev != vdev)
            continue;
        if (entry->state.quiesced != MISHARE_QUIESCE_SSR)
            break;
        if (!radio_token || entry->radio != radio_token ||
            !entry->state.ndi.radio_requested || entry->state.ndi.radio_submit_error ||
            entry->state.recovery_radio_start_flushed || entry->state.recovery_radio_start_refused ||
            entry->state.recovery_radio_start_aborted || entry->state.recovery_radio_prepared_aborted ||
            entry->state.recovery_radio_sm_entry_aborted || entry->state.recovery_radio_init_rejected ||
            entry->state.recovery_radio_released || entry->state.ndi_reclaim_started) {
            if (!entry->state.ndi.completion_error)
                entry->state.ndi.completion_error = -EUCLEAN;
        } else {
            if (origin == MISHARE_CANCEL_INIT_REJECT)
                entry->state.recovery_radio_init_rejected = true;
            else if (origin == MISHARE_CANCEL_SM_ENTRY_ABORT)
                entry->state.recovery_radio_sm_entry_aborted = true;
            else if (origin == MISHARE_CANCEL_REFUSAL)
                entry->state.recovery_radio_start_refused = true;
            else if (origin == MISHARE_CANCEL_PREPARED_ABORT)
                entry->state.recovery_radio_prepared_aborted = true;
            else if (origin == MISHARE_CANCEL_BODY_ABORT)
                entry->state.recovery_radio_start_aborted = true;
            else
                entry->state.recovery_radio_start_flushed = true;
        }
        break;
    }
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
}

void mishare_runtime_radio_start_flushed(struct wlan_objmgr_psoc *psoc,
                                         struct wlan_objmgr_vdev *vdev,
                                         void *owner, void *radio_token)
{
    mishare_runtime_radio_cancel_origin(psoc, vdev, owner, radio_token, MISHARE_CANCEL_FLUSH);
}

void mishare_runtime_radio_start_refused(struct wlan_objmgr_psoc *psoc,
                                         struct wlan_objmgr_vdev *vdev,
                                         void *owner, void *radio_token)
{
    mishare_runtime_radio_cancel_origin(psoc, vdev, owner, radio_token, MISHARE_CANCEL_REFUSAL);
}

void mishare_runtime_radio_start_aborted(struct wlan_objmgr_psoc *psoc,
                                         struct wlan_objmgr_vdev *vdev,
                                         void *owner, void *radio_token)
{
    mishare_runtime_radio_cancel_origin(psoc, vdev, owner, radio_token, MISHARE_CANCEL_BODY_ABORT);
}

void mishare_runtime_radio_prepared_aborted(struct wlan_objmgr_psoc *psoc,
                                            struct wlan_objmgr_vdev *vdev,
                                            void *owner, void *radio_token)
{
    mishare_runtime_radio_cancel_origin(psoc, vdev, owner, radio_token, MISHARE_CANCEL_PREPARED_ABORT);
}

void mishare_runtime_radio_sm_entry_aborted(struct wlan_objmgr_psoc *psoc,
                                            struct wlan_objmgr_vdev *vdev,
                                            void *owner, void *radio_token)
{
    mishare_runtime_radio_cancel_origin(psoc, vdev, owner, radio_token, MISHARE_CANCEL_SM_ENTRY_ABORT);
}

void mishare_runtime_radio_init_rejected(struct wlan_objmgr_psoc *psoc,
                                         struct wlan_objmgr_vdev *vdev,
                                         void *owner, void *radio_token)
{
    mishare_runtime_radio_cancel_origin(psoc, vdev, owner, radio_token, MISHARE_CANCEL_INIT_REJECT);
}

bool mishare_runtime_any_busy(void)
{
    unsigned long flags;
    bool busy;

    spin_lock_irqsave(&mishare_runtime_lock, flags);
    busy = mishare_runtime_owners != NULL;
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    return busy;
}

bool mishare_runtime_psoc_busy(struct wlan_objmgr_psoc *psoc)
{
    struct mishare_runtime_owner *entry;
    unsigned long flags;
    bool busy = false;

    if (!psoc)
        return false;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    for (entry = mishare_runtime_owners; entry; entry = entry->next) {
        if (entry->psoc == psoc) {
            busy = true;
            break;
        }
    }
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    return busy;
}

unsigned int mishare_runtime_quiesce_psoc(struct wlan_objmgr_psoc *psoc,
                                          enum mishare_quiesce_reason reason)
{
    struct mishare_runtime_owner *entry;
    unsigned long flags;
    unsigned int count = 0;
    if (!psoc || reason <= MISHARE_QUIESCE_NONE ||
        reason > MISHARE_QUIESCE_UNAVAILABLE)
        return 0;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    for (entry = mishare_runtime_owners; entry; entry = entry->next) {
        if (entry->psoc != psoc)
            continue;
        count++;
        if (!entry->state.quiesced) {
            if (reason == MISHARE_QUIESCE_SSR && !entry->state.blocked &&
                !entry->state.ndi.blocked && mishare_runtime_rate_delete_inflight(entry))
                entry->state.rate.late_delete_armed = true;
            if (reason == MISHARE_QUIESCE_SSR && !entry->state.blocked &&
                !entry->state.ndi.blocked && mishare_runtime_rate_peer_inflight(entry))
                entry->state.rate.late_peer_armed = true;
            if (reason == MISHARE_QUIESCE_SSR && !entry->state.blocked &&
                !entry->state.ndi.blocked && mishare_runtime_rate_peer_ready(entry))
                entry->state.rate.peer_reset_armed = true;
            entry->state.quiesced = reason;
        }
        entry->state.blocked = true;
        entry->state.ndi.blocked = true;
    }
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    /* Separate locks, no nested registry lock or retained owner pointer. */
    mishare_events_quiesce_psoc(psoc);
    mishare_radio_quiesce_psoc(psoc);
    return count;
}

static bool mishare_runtime_work_identity(struct wlan_objmgr_vdev *vdev,
                                           void *owner,
                                           struct wlan_objmgr_psoc *psoc)
{
    struct mishare_runtime_owner *entry;
    unsigned long flags;
    bool allowed = false;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    for (entry = mishare_runtime_owners; entry; entry = entry->next) {
        if (entry != owner || entry->psoc != psoc || entry->vdev != vdev)
            continue;
        allowed = !entry->state.blocked && !entry->state.ndi.blocked &&
                  !entry->state.quiesced && !entry->state.draining;
        break;
    }
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    return allowed;
}

bool mishare_runtime_work_allowed(struct wlan_objmgr_vdev *vdev, void *owner)
{
    struct wlan_objmgr_psoc *psoc;
    if (!vdev || !owner)
        return false;
    psoc = wlan_vdev_get_psoc(vdev);
    /* Reject foreign/fenced tokens before touching native HDD context. */
    if (!mishare_runtime_work_identity(vdev, owner, psoc))
        return false;
    if (!mishare_runtime_platform_available(psoc)) {
        mishare_runtime_quiesce_psoc(psoc, MISHARE_QUIESCE_UNAVAILABLE);
        return false;
    }
    /* Shutdown can close admission while the health snapshot is taken. */
    return mishare_runtime_work_identity(vdev, owner, psoc);
}

static void mishare_runtime_work_update(struct mishare_runtime_owner *entry)
{
    entry->state.mc_drained = entry->state.quiesced && entry->state.mc_stop_seen &&
                              !entry->state.work_pending && !entry->state.work_users &&
                              !entry->state.work_error;
}

enum mishare_work_action { MISHARE_WORK_GET, MISHARE_WORK_ENTER,
                          MISHARE_WORK_EXIT, MISHARE_WORK_PUT };
static int mishare_runtime_work_change(struct wlan_objmgr_vdev *vdev, void *owner,
                                        enum mishare_work_action action)
{
    struct mishare_runtime_owner *entry;
    unsigned long flags;
    int ret = -ENOENT;
    if (!vdev || !owner)
        return -EINVAL;
    if ((action == MISHARE_WORK_GET || action == MISHARE_WORK_ENTER) &&
        !mishare_runtime_work_allowed(vdev, owner))
        return -ESHUTDOWN;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    for (entry = mishare_runtime_owners; entry; entry = entry->next) {
        if (entry != owner || entry->vdev != vdev ||
            entry->psoc != wlan_vdev_get_psoc(vdev))
            continue;
        ret = 0;
        if ((action == MISHARE_WORK_GET || action == MISHARE_WORK_ENTER) &&
            (entry->state.blocked || entry->state.ndi.blocked ||
             entry->state.quiesced || entry->state.draining)) {
            ret = -ESHUTDOWN;
            break;
        }
        switch (action) {
        case MISHARE_WORK_GET:
            if (entry->state.work_pending == ~0U)
                ret = -EOVERFLOW;
            else
                entry->state.work_pending++;
            break;
        case MISHARE_WORK_ENTER:
            if (entry->state.work_users >= entry->state.work_pending)
                ret = -EUCLEAN;
            else
                entry->state.work_users++;
            break;
        case MISHARE_WORK_EXIT:
            if (!entry->state.work_users)
                ret = -EUCLEAN;
            else
                entry->state.work_users--;
            break;
        case MISHARE_WORK_PUT:
            if (entry->state.work_pending <= entry->state.work_users)
                ret = -EUCLEAN;
            else
                entry->state.work_pending--;
            break;
        }
        if (ret) {
            entry->state.blocked = true;
            entry->state.ndi.blocked = true;
            if (!entry->state.work_error)
                entry->state.work_error = ret;
        }
        mishare_runtime_work_update(entry);
        break;
    }
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    return ret;
}
int mishare_runtime_work_get(struct wlan_objmgr_vdev *vdev, void *owner)
{
    return mishare_runtime_work_change(vdev, owner, MISHARE_WORK_GET);
}
int mishare_runtime_work_enter(struct wlan_objmgr_vdev *vdev, void *owner)
{
    return mishare_runtime_work_change(vdev, owner, MISHARE_WORK_ENTER);
}
void mishare_runtime_work_exit(struct wlan_objmgr_vdev *vdev, void *owner)
{
    mishare_runtime_work_change(vdev, owner, MISHARE_WORK_EXIT);
}
void mishare_runtime_work_put(struct wlan_objmgr_vdev *vdev, void *owner)
{
    mishare_runtime_work_change(vdev, owner, MISHARE_WORK_PUT);
}
void mishare_runtime_mc_stopped(struct wlan_objmgr_psoc *psoc)
{
    struct mishare_runtime_owner *entry;
    unsigned long flags;
    if (!psoc)
        return;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    for (entry = mishare_runtime_owners; entry; entry = entry->next) {
        if (entry->psoc != psoc || !entry->state.quiesced)
            continue;
        entry->state.mc_stop_seen = true;
        mishare_runtime_work_update(entry);
    }
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
}

void mishare_runtime_allocated(struct wlan_objmgr_vdev *vdev)
{
    struct mishare_runtime_owner *entry;
    unsigned long flags;

    if (wlan_vdev_mlme_get_opmode(vdev) != QDF_PASSTHRU_MODE)
        return;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    for (entry = mishare_runtime_owners; entry; entry = entry->next) {
        if (entry->psoc != wlan_vdev_get_psoc(vdev) || entry->state.allocated ||
            !ether_addr_equal(entry->mac, wlan_vdev_mlme_get_macaddr(vdev)))
            continue;
        entry->cookie = (unsigned long)vdev;
        entry->state.allocated = true;
        break;
    }
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
}

bool mishare_runtime_prepare_free(struct wlan_objmgr_vdev *vdev,
                                   unsigned long *owner_token)
{
    struct mishare_runtime_owner *entry;
    unsigned long flags;
    unsigned int id;
    bool allowed = true;

    if (!owner_token)
        return false;
    *owner_token = 0;
    if (wlan_vdev_mlme_get_opmode(vdev) != QDF_PASSTHRU_MODE)
        return true;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    for (entry = mishare_runtime_owners; entry; entry = entry->next) {
        if (entry->cookie != (unsigned long)vdev || entry->state.freed ||
            entry->psoc != wlan_vdev_get_psoc(vdev))
            continue;
        /* Some native component failures leave an attached private object.
         * Never release its vdev/ID/netdev underneath it. No refcount reset.
         */
        if (entry->state.ndi.active) {
            entry->state.blocked = true;
            allowed = false;
            break;
        }
        for (id = 0; id < WLAN_UMAC_MAX_COMPONENTS; id++) {
            if (vdev->vdev_comp_priv_obj[id]) {
                entry->state.blocked = true;
                if (entry->state.host_reclaim || entry->state.ndi_reclaim_ready ||
                    entry->state.host_delete_accepted)
                    entry->state.reclaim_error = -EUCLEAN;
                allowed = false;
                break;
            }
        }
        if (allowed)
            *owner_token = (unsigned long)entry;
        break;
    }
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    return allowed;
}

void mishare_runtime_freed(struct wlan_objmgr_psoc *psoc, unsigned long owner_token)
{
    struct mishare_runtime_owner *entry;
    unsigned long flags;

    spin_lock_irqsave(&mishare_runtime_lock, flags);
    for (entry = mishare_runtime_owners; entry; entry = entry->next) {
        if (entry->psoc == psoc && (unsigned long)entry == owner_token &&
            entry->state.allocated && !entry->state.freed) {
            entry->state.freed = true;
            if (!entry->state.quiesced)
                entry->state.blocked = false;
            break;
        }
    }
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
}

int mishare_runtime_snapshot(struct mishare_runtime_owner *owner,
                             struct mishare_runtime_status *status)
{
    struct mishare_runtime_owner *entry;
    struct mishare_radio *radio;
    struct mishare_radio_status observed = {0};
    unsigned long flags;
    int ret;

    if (!owner || !status)
        return -EINVAL;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    for (entry = mishare_runtime_owners; entry && entry != owner; entry = entry->next)
        ;
    if (!entry) {
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return -ENOENT;
    }
    radio = entry->radio;
    if (!radio) {
        *status = entry->state;
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return 0;
    }
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    /* No registry locks nest. Caller still retains/serializes native parents;
     * this observation acquires no lifetime reference or teardown authority. */
    ret = mishare_radio_snapshot(radio, &observed);
    if (ret)
        return ret;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    for (entry = mishare_runtime_owners; entry && entry != owner; entry = entry->next)
        ;
    if (!entry)
        ret = -ENOENT;
    else if (entry->radio != radio)
        ret = -EUCLEAN;
    else {
        *status = entry->state;
        status->radio = observed;
        ret = 0;
    }
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    return ret;
}

/* Registry lock held, scalar/handle presence only. No native dereference. */
static bool mishare_runtime_down_origin_valid(struct mishare_runtime_owner *e)
{
    const struct mishare_radio_status *r = &e->state.radio;
    const struct mishare_radio_fence_status *f = &r->fence;

    return e->state.recovery_down_observed && e->state.quiesced == MISHARE_QUIESCE_SSR &&
           !e->state.rate.requested && !e->state.retry.requested && !e->state.start_preview.requested &&
           !e->state.recovery_radio_released && !e->state.recovery_radio_start_flushed &&
           !e->state.recovery_radio_start_refused && !e->state.recovery_radio_start_aborted &&
           !e->state.recovery_radio_prepared_aborted && !e->state.recovery_radio_sm_entry_aborted &&
           !e->state.recovery_radio_init_rejected && !e->state.ndi.radio_submit_error &&
           e->state.ndi.radio_requested && f->recorded && f->phase == MISHARE_RADIO_DOWN &&
           !f->error && f->closing && f->start_attempted && f->stop_attempted && f->host_up &&
           f->down_attempted && f->down_accepted && !f->pending && !f->users &&
           r->phase == MISHARE_RADIO_BLOCKED && r->error == -ESHUTDOWN && r->closing &&
           r->start_attempted && r->stop_attempted && r->host_up && r->down_attempted && r->down_accepted &&
           !r->pending && !r->users && !r->ssr_cancelled_before_start &&
           !r->down_retire_error && !r->down_fence_callback_seen &&
           (e->state.recovery_down_released ?
            (!e->radio && r->down_retired && r->down_retire_timer_attempted && r->down_retire_timer_released &&
             e->state.recovery_timer_attempted && e->state.recovery_timer_released && !e->state.ndi.create.timer_ready) :
            (e->radio && !r->down_retired && !r->down_retire_timer_attempted && !r->down_retire_timer_released));
}

static bool mishare_runtime_down_completion_valid(struct mishare_runtime_owner *e)
{
    return mishare_runtime_down_origin_valid(e) && e->state.recovery_down_released &&
           e->state.ndi_reclaim_ready && e->state.recovery_pe_released && !e->pe_cookie &&
           e->state.recovery_peer_released && e->state.recovery_dp_freed &&
           e->state.recovery_context_released && !e->state.ndi.active && !e->state.ndi.pe_ready &&
           !e->state.ndi.peer_created && !e->state.ndi.legacy_ready && !e->state.ndi.wma_bound &&
           !e->state.ndi.create.dp_attached && !e->state.ndi.create.stats_owned;
}

/* Parent serialization keeps the authenticated owner and native handles alive
 * across the unlocked native component check. No new work or cleanup here. */
int mishare_runtime_fenced_down_prepare(struct mishare_runtime_owner *owner)
{
    struct mishare_runtime_owner *e;
    struct mishare_radio *radio;
    struct wlan_objmgr_vdev *vdev;
    struct mishare_event_owner *events;
    struct mishare_radio_status observed = {0};
    unsigned long flags, cookie;
    u32 freq;
    int ret = -ENOENT;

    if (!owner)
        return -EINVAL;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    for (e = mishare_runtime_owners; e && e != owner; e = e->next)
        ;
    if (!e)
        goto unlock;
    if (e->state.quiesced != MISHARE_QUIESCE_SSR || e->state.recovery_window_closed ||
        e->state.draining || e->state.freed) {
        ret = -ESHUTDOWN;
        goto unlock;
    }
    if (!e->state.mc_drained || e->state.work_pending || e->state.work_users) {
        ret = -EINPROGRESS;
        goto unlock;
    }
    if (e->state.rate.requested || e->state.retry.requested || e->state.start_preview.requested) {
        ret = -EOPNOTSUPP;
        goto unlock;
    }
    if (!e->vdev || !e->referenced || !e->events || !e->radio || !e->pe_cookie ||
        e->cookie != (unsigned long)e->vdev || !e->state.allocated ||
        e->state.work_error || e->state.recovery_error || e->state.reclaim_error ||
        e->state.ndi.completion_error || e->state.ndi_reclaim_started || e->state.host_reclaim ||
        e->state.recovery_down_released || e->state.recovery_radio_released ||
        e->state.recovery_timer_attempted || e->state.recovery_context_attempted ||
        e->state.recovery_pe_attempted || e->state.recovery_dp_attempted ||
        !e->state.ndi.active || !e->state.ndi.legacy_ready || !e->state.ndi.wma_bound ||
        !e->state.ndi.peer_created || !e->state.ndi.pe_ready || !e->state.ndi.channel_prepared ||
        !e->state.ndi.start_plan_ready || !e->state.ndi.radio_requested || e->state.ndi.radio_submit_error ||
        !e->state.ndi.create.timer_ready || !e->state.ndi.create.dp_attached ||
        e->state.ndi.pe_delete_requested || e->state.ndi.peer_delete_pending ||
        e->state.ndi.delete_pending || e->state.ndi.dp_detaching) {
        ret = -EUCLEAN;
        goto unlock;
    }
    if ((e->state.recovery_down_observed &&
         (!mishare_runtime_down_origin_valid(e) || e->state.recovery_down_vdev_id != wlan_vdev_get_id(e->vdev))) ||
        e->state.recovery_radio_start_flushed || e->state.recovery_radio_start_refused ||
        e->state.recovery_radio_start_aborted || e->state.recovery_radio_prepared_aborted ||
        e->state.recovery_radio_sm_entry_aborted || e->state.recovery_radio_init_rejected ||
        (!e->state.recovery_down_observed && e->state.recovery_window)) {
        ret = -EUCLEAN;
        goto unlock;
    }
    radio = e->radio; vdev = e->vdev; events = e->events;
    cookie = e->pe_cookie; freq = e->state.ndi.channel_freq;
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    ret = mishare_radio_fenced_down_check(radio, vdev, events, owner, cookie, freq);
    if (!ret)
        ret = mishare_radio_snapshot(radio, &observed);
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    if (!ret && (e->radio != radio || e->vdev != vdev || e->events != events || e->pe_cookie != cookie ||
                 e->state.quiesced != MISHARE_QUIESCE_SSR || !e->state.mc_drained ||
                 e->state.recovery_window_closed || e->state.draining || e->state.work_error ||
                 e->state.work_pending || e->state.work_users))
        ret = -EUCLEAN;
    if (!ret) {
        e->state.radio = observed;
        e->state.recovery_down_vdev_id = wlan_vdev_get_id(vdev);
        e->state.recovery_down_observed = true;
        if (!mishare_runtime_down_origin_valid(e))
            ret = -EUCLEAN;
    }
unlock:
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    return ret;
}

/* Event evidence is preserved for the completed DOWN route, never reset to
 * cold/serial zero to fit the pre-START recovery policy. */
static bool mishare_runtime_recovery_txn_valid(struct mishare_runtime_owner *e,
                                               const struct mishare_vdev_txn *txn)
{
    if (txn->state != MISHARE_TXN_QUARANTINED || txn->pending != MISHARE_TXN_NONE)
        return false;
    return e->state.recovery_down_observed ?
           (mishare_runtime_down_origin_valid(e) && txn->vdev_id == e->state.recovery_down_vdev_id &&
            txn->serial == 2 && txn->submitted && txn->replied) :
           (!txn->serial && !txn->submitted && !txn->replied);
}

static int mishare_runtime_host_destroy(struct mishare_runtime_owner **owner, bool reclaim)
{
    struct mishare_runtime_owner *entry, **link;
    struct wlan_objmgr_vdev *vdev;
    unsigned long flags;
    QDF_STATUS status;
    bool referenced;
    int ret;

    if (!owner)
        return -EINVAL;
    entry = *owner;
    if (!entry)
        return 0;
    if (!reclaim) {
        ret = mishare_runtime_ndi_drain(entry);
        if (ret)
            return ret;
    }
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    ret = reclaim && entry->state.rate.peer_reset_completed ?
          mishare_runtime_rate_peer_reset_check(entry) :
          reclaim && entry->state.rate.tail_completed ?
          mishare_runtime_rate_tail_check(entry) :
          reclaim && entry->state.rate.reset_completed ?
          mishare_runtime_rate_reset_check(entry) :
          (!reclaim && entry->state.rate.ordinary_completed ?
           mishare_runtime_rate_ordinary_check(entry) : mishare_runtime_rate_retire_check(entry));
    if (ret) {
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return ret;
    }

    if (reclaim && (entry->state.recovery_down_observed || entry->state.recovery_down_released) &&
        !mishare_runtime_down_completion_valid(entry)) {
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return -EUCLEAN;
    }
    if (entry->state.ndi.completion_error || (entry->state.blocked && !reclaim)) {
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return -EUCLEAN;
    }
    if (entry->state.work_pending || entry->state.work_users) {
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return -EINPROGRESS;
    }
    if (!entry->state.draining && entry->vdev) {
        entry->state.draining = true;
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        vdev = entry->vdev;
        status = wlan_objmgr_vdev_obj_delete(vdev);
        if (status != QDF_STATUS_SUCCESS) {
            spin_lock_irqsave(&mishare_runtime_lock, flags);
            entry->state.blocked = true;
            if (reclaim)
                entry->state.reclaim_error = -EUCLEAN;
            spin_unlock_irqrestore(&mishare_runtime_lock, flags);
            return -EUCLEAN;
        }
        /* The owned reference prevents physical destruction until observers
         * are removed. No registry lock is held across either ref release.
         */
        mishare_events_unbind(&entry->events);
        if (entry->events) {
            spin_lock_irqsave(&mishare_runtime_lock, flags);
            entry->state.blocked = true;
            if (reclaim)
                entry->state.reclaim_error = -EUCLEAN;
            spin_unlock_irqrestore(&mishare_runtime_lock, flags);
            return -EUCLEAN;
        }
        referenced = entry->referenced;
        entry->referenced = false;
        entry->vdev = NULL;
        spin_lock_irqsave(&mishare_runtime_lock, flags);
        entry->state.host_delete_accepted = true;
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        if (referenced)
            wlan_objmgr_vdev_release_ref(vdev, WLAN_HDD_ID_OBJ_MGR);
        spin_lock_irqsave(&mishare_runtime_lock, flags);
    }
    if (entry->state.ndi.completion_error || (entry->state.blocked && !reclaim)) {
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return -EUCLEAN;
    }
    if (entry->state.allocated && !entry->state.freed) {
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return -EINPROGRESS;
    }
    for (link = &mishare_runtime_owners; *link && *link != entry;
         link = &(*link)->next)
        ;
    if (!*link) {
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return -EUCLEAN;
    }
    *link = entry->next;
    *owner = NULL;
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    kfree(entry);
    module_put(THIS_MODULE);
    return 0;
}

int mishare_runtime_destroy(struct mishare_runtime_owner **owner)
{
    return mishare_runtime_host_destroy(owner, false);
}

int mishare_runtime_reclaim_host(struct mishare_runtime_owner **owner)
{
    struct mishare_runtime_owner *entry;
    struct mishare_ndi_status *ndi;
    struct vdev_mlme_obj *mlme;
    struct mishare_vdev_txn txn;
    unsigned long flags;
    int ret = 0;
    if (!owner)
        return -EINVAL;
    entry = *owner;
    if (!entry)
        return 0;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    ret = mishare_runtime_rate_retire_check(entry);
    if (ret) {
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return ret;
    }

    ndi = &entry->state.ndi;
    if (!entry->state.quiesced || entry->state.work_error || entry->state.reclaim_error ||
        entry->state.recovery_error ||
        ndi->completion_error ||
        entry->state.ndi_reclaim_started)
        ret = -EUCLEAN;
    else if (!entry->state.mc_drained || entry->state.work_pending || entry->state.work_users)
        ret = -EINPROGRESS;
    else if (!entry->state.host_reclaim) {
        /* These are host-only admission facts, never a firmware-reset claim. */
        if (!entry->vdev || !entry->referenced || !entry->events || entry->radio ||
            !entry->state.allocated || entry->state.freed || entry->state.draining ||
            entry->cookie != (unsigned long)entry->vdev || entry->pe_cookie ||
            ndi->active || ndi->create.timer_ready || ndi->create.wire_attempted ||
            ndi->create.wire_accepted || ndi->create.dp_attempted || ndi->create.dp_attached ||
            ndi->create.stats_owned || ndi->legacy_ready || ndi->wma_bound ||
            ndi->delete_pending || ndi->delete_submitted || ndi->delete_replied ||
            ndi->dp_detaching || ndi->dp_detach_submitted || ndi->dp_freed || ndi->peer_delete_pending ||
            ndi->peer_create_attempted || ndi->peer_created || ndi->pe_requested ||
            ndi->channel_requested || ndi->start_plan_requested || ndi->radio_requested)
            ret = -EUCLEAN;
    }
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    if (ret)
        return ret;
    if (!entry->state.host_reclaim) {
        if (mishare_events_snapshot(entry->events, &txn) ||
            txn.state != MISHARE_TXN_QUARANTINED || txn.serial ||
            txn.pending != MISHARE_TXN_NONE || txn.submitted || txn.replied)
            return -EUCLEAN;
        mlme = wlan_vdev_mlme_get_cmpt_obj(entry->vdev);
        if (!mlme || mlme->vdev != entry->vdev || mlme->ext_vdev_ptr ||
            wlan_vdev_mlme_get_opmode(entry->vdev) != QDF_PASSTHRU_MODE ||
            mlme->mgmt.generic.type != WLAN_VDEV_MLME_TYPE_PASSTHRU ||
            mlme->mgmt.generic.subtype ||
            wlan_vdev_mlme_get_state(entry->vdev) != WLAN_VDEV_S_INIT)
            return -EUCLEAN;
        spin_lock_irqsave(&mishare_runtime_lock, flags);
        entry->state.host_reclaim = true;
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    }
    return mishare_runtime_host_destroy(owner, true);
}

/* Caller holds the registry lock. Only observed ordinary completions qualify;
 * no prepared context, peer, PE, radio or reset cleanup is inferred.
 */
static bool mishare_runtime_ndi_completed_candidate(struct mishare_runtime_owner *entry)
{
    struct mishare_ndi_status *n = &entry->state.ndi;

    if (mishare_runtime_rate_retire_check(entry))
        return false;
    return entry->state.quiesced == MISHARE_QUIESCE_SSR &&
           entry->state.mc_drained && !entry->state.work_pending && !entry->state.work_users &&
           !entry->state.work_error && !entry->state.reclaim_error && !entry->state.recovery_error &&
           !n->completion_error && !entry->state.recovery_window_closed &&
           !entry->state.ndi_reclaim_started && !entry->state.ndi_reclaim_ready &&
           !entry->state.recovery_radio_start_flushed && !entry->state.recovery_radio_start_refused &&
           !entry->state.recovery_radio_start_aborted && !entry->state.recovery_radio_prepared_aborted &&
           !entry->state.recovery_radio_sm_entry_aborted && !entry->state.recovery_radio_init_rejected &&
           !entry->state.recovery_radio_released &&
           !entry->state.recovery_pe_attempted && !entry->state.recovery_pe_released &&
           !entry->state.recovery_context_attempted && !entry->state.recovery_context_released &&
           !entry->state.recovery_peer_released && !entry->state.recovery_context_finish_attempted &&
           !entry->state.recovery_timer_attempted && !entry->state.recovery_timer_released &&
           !entry->state.ndi_completed_reclaim && !entry->state.recovery_dp_attempted &&
           !entry->state.recovery_dp_freed && !entry->state.host_reclaim &&
           !entry->state.draining && entry->state.allocated && !entry->state.freed &&
           entry->vdev && entry->referenced && entry->events && !entry->radio &&
           entry->cookie == (unsigned long)entry->vdev && !entry->pe_cookie &&
           n->active && !n->create_error && !n->create.timer_ready &&
           n->create.wire_attempted && n->create.wire_accepted &&
           n->create.dp_attempted && n->create.dp_attached && n->create.dp_cookie &&
           !n->create.stats_owned && !n->legacy_ready && !n->wma_bound && !n->context_error &&
           !n->peer_create_attempted && !n->peer_created && !n->peer_delete_pending &&
           !n->peer_delete_submitted && !n->peer_delete_replied &&
           !n->pe_requested && !n->pe_submitted && !n->pe_completed && !n->pe_ready &&
           !n->pe_delete_requested && !n->pe_delete_submitted && !n->pe_delete_completed &&
           !n->channel_requested && !n->channel_submitted && !n->channel_completed &&
           !n->channel_prepared && !n->start_plan_requested && !n->start_plan_submitted &&
           !n->start_plan_completed && !n->start_plan_ready && !n->radio_requested && !n->radio_submit_error &&
           n->delete_pending && n->delete_submitted && n->delete_replied &&
           n->dp_detaching && n->dp_detach_submitted && n->dp_freed;
}

/* No wire commands or state-machine events occur on this recovery route. */
/* Pure origin metadata, called under the runtime registry lock. */
static bool mishare_runtime_radio_origin_valid(struct mishare_runtime_owner *entry)
{
    unsigned int count = entry->state.recovery_radio_start_flushed +
                         entry->state.recovery_radio_start_refused +
                         entry->state.recovery_radio_start_aborted +
                         entry->state.recovery_radio_prepared_aborted +
                         entry->state.recovery_radio_sm_entry_aborted +
                         entry->state.recovery_radio_init_rejected +
                         (entry->state.ndi.radio_submit_error != 0);

    return count == 1;
}

static bool mishare_runtime_ndi_recovery_candidate(struct mishare_runtime_owner *entry)
{
    struct mishare_ndi_status *n = &entry->state.ndi;
    bool early, prepared, no_pe, ready_pe, no_channel, ready_channel, no_plan, ready_plan;
    bool no_radio, cancelled_radio, completed_down;

    early = !entry->state.recovery_context_attempted &&
            !entry->state.recovery_context_released && !n->legacy_ready &&
            !n->wma_bound && !n->peer_create_attempted && !n->peer_created;
    prepared = !entry->state.recovery_context_attempted &&
               !entry->state.recovery_context_released && n->legacy_ready &&
               n->wma_bound && n->peer_create_attempted && n->peer_created;
    no_pe = !entry->pe_cookie && !n->pe_requested && !n->pe_submitted &&
            !n->pe_completed && !n->pe_ready;
    ready_pe = prepared && entry->pe_cookie && n->pe_requested &&
               n->pe_submitted && n->pe_completed && n->pe_ready;
    no_channel = !n->channel_requested && !n->channel_submitted &&
                 !n->channel_completed && !n->channel_prepared && !n->channel_freq &&
                 !n->channel_error;
    ready_channel = ready_pe && n->channel_requested && n->channel_submitted &&
                    n->channel_completed && n->channel_prepared && n->channel_freq &&
                    !n->channel_error;
    no_plan = !n->start_plan_requested && !n->start_plan_submitted &&
              !n->start_plan_completed && !n->start_plan_ready && !n->start_plan_error &&
              !n->start_plan.freq && !n->start_plan.center_freq && !n->start_plan.phy_mode &&
              !n->start_plan.tx_streams && !n->start_plan.rx_streams &&
              !n->start_plan.beacon_interval && !n->start_plan.dtim_period;
    ready_plan = ready_channel && n->start_plan_requested && n->start_plan_submitted &&
                 n->start_plan_completed && n->start_plan_ready && !n->start_plan_error &&
                 n->start_plan.freq == n->channel_freq &&
                 n->start_plan.center_freq == n->channel_freq && n->start_plan.phy_mode &&
                 n->start_plan.tx_streams && n->start_plan.tx_streams <= 2 &&
                 n->start_plan.rx_streams == n->start_plan.tx_streams;
    no_radio = !n->radio_requested && !n->radio_submit_error && !entry->radio &&
               !entry->state.recovery_radio_start_flushed && !entry->state.recovery_radio_start_refused &&
               !entry->state.recovery_radio_start_aborted && !entry->state.recovery_radio_prepared_aborted &&
           !entry->state.recovery_radio_sm_entry_aborted && !entry->state.recovery_radio_init_rejected &&
           !entry->state.recovery_radio_released;
    cancelled_radio = ready_plan && n->radio_requested &&
                      mishare_runtime_radio_origin_valid(entry) &&
                      ((!entry->state.recovery_radio_released && entry->radio) ||
                       (entry->state.recovery_radio_released && !entry->radio &&
                        entry->state.radio.ssr_cancelled_before_start &&
                        entry->state.radio.ssr_start_submit_error == n->radio_submit_error &&
                        entry->state.radio.ssr_start_callback_refused == entry->state.recovery_radio_start_refused &&
             entry->state.radio.ssr_start_body_aborted == entry->state.recovery_radio_start_aborted &&
             entry->state.radio.ssr_start_prepared_aborted == entry->state.recovery_radio_prepared_aborted &&
             entry->state.radio.ssr_start_sm_entry_aborted == entry->state.recovery_radio_sm_entry_aborted &&
             entry->state.radio.ssr_start_init_rejected == entry->state.recovery_radio_init_rejected &&
                        !entry->state.radio.start_attempted && !entry->state.radio.host_up &&
                        !entry->state.radio.stop_attempted && !entry->state.radio.down_attempted &&
                        !entry->state.radio.down_accepted));
    completed_down = ready_plan && mishare_runtime_down_origin_valid(entry);
    if (mishare_runtime_rate_reset_check(entry))
        return false;
    return entry->state.quiesced == MISHARE_QUIESCE_SSR &&
           entry->state.mc_drained && !entry->state.work_pending && !entry->state.work_users &&
           !entry->state.work_error && !entry->state.reclaim_error && !entry->state.recovery_error &&
           !n->completion_error &&
           !entry->state.recovery_window_closed && !entry->state.ndi_reclaim_started &&
           !entry->state.host_reclaim && !entry->state.draining &&
           entry->vdev && entry->referenced && entry->events && (no_radio || cancelled_radio || completed_down) &&
           entry->cookie == (unsigned long)entry->vdev && (no_pe || ready_pe) &&
           n->active && !n->create_error && n->create.timer_ready &&
           n->create.wire_attempted && n->create.wire_accepted &&
           n->create.dp_attempted && n->create.dp_attached && n->create.dp_cookie &&
           n->create.stats_owned && !n->context_error && (early || prepared) &&
           !entry->state.recovery_peer_released && !entry->state.recovery_context_finish_attempted &&
           !entry->state.recovery_pe_attempted && !entry->state.recovery_pe_released &&
           !n->peer_delete_pending && !n->peer_delete_submitted && !n->peer_delete_replied &&
           !n->pe_error && (no_channel || ready_channel) && (no_plan || ready_plan) &&
           !n->pe_delete_requested && !n->pe_delete_submitted && !n->pe_delete_completed &&
           !n->delete_pending && !n->delete_submitted && !n->delete_replied &&
           !n->dp_detaching && !n->dp_detach_submitted && !n->dp_freed;
}
unsigned int mishare_runtime_recovery_candidates(struct wlan_objmgr_psoc *psoc)
{
    struct mishare_runtime_owner *entry;
    unsigned long flags;
    unsigned int count = 0;
    if (!psoc)
        return 0;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    for (entry = mishare_runtime_owners; entry; entry = entry->next)
        if (entry->psoc == psoc && ((entry->state.rate.ordinary_admitted &&
                                    !entry->state.rate.peer_reset_completed &&
                                    !entry->state.rate.peer_finish_attempted &&
                                    !mishare_runtime_rate_peer_reset_check(entry)) ||
                                   mishare_runtime_ndi_recovery_candidate(entry) ||
                                   mishare_runtime_ndi_completed_candidate(entry) ||
                                   (entry->state.rate.ordinary_admitted &&
                                    !entry->state.rate.tail_attempted &&
                                    !entry->state.rate.ordinary_completed &&
                                    !mishare_runtime_rate_tail_check(entry))))
            count++;
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    return count;
}
void mishare_runtime_recovery_open(struct wlan_objmgr_psoc *psoc)
{
    struct mishare_runtime_owner *entry;
    unsigned long flags;
    if (!psoc)
        return;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    for (entry = mishare_runtime_owners; entry; entry = entry->next)
        if (entry->psoc == psoc && ((entry->state.rate.ordinary_admitted &&
                                    !entry->state.rate.peer_reset_completed &&
                                    !entry->state.rate.peer_finish_attempted &&
                                    !mishare_runtime_rate_peer_reset_check(entry)) ||
                                   mishare_runtime_ndi_recovery_candidate(entry) ||
                                   mishare_runtime_ndi_completed_candidate(entry) ||
                                   (entry->state.rate.ordinary_admitted &&
                                    !entry->state.rate.tail_attempted &&
                                    !entry->state.rate.ordinary_completed &&
                                    !mishare_runtime_rate_tail_check(entry))))
            entry->state.recovery_window = true;
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
}
void mishare_runtime_recovery_close(struct wlan_objmgr_psoc *psoc)
{
    struct mishare_runtime_owner *entry;
    unsigned long flags;
    if (!psoc)
        return;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    for (entry = mishare_runtime_owners; entry; entry = entry->next) {
        if (entry->psoc != psoc)
            continue;
        entry->state.recovery_window = false;
        entry->state.recovery_window_closed = true;
    }
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
}
static void mishare_runtime_recovery_dp_freed(void *context)
{
    struct mishare_runtime_owner *entry;
    struct mishare_ndi_status *n;
    unsigned long flags;

    spin_lock_irqsave(&mishare_runtime_lock, flags);
    for (entry = mishare_runtime_owners; entry; entry = entry->next) {
        if (entry != context)
            continue;
        n = &entry->state.ndi;
        /* A known token on the wrong route is an error, not an absent owner.
         * Inline native completion is allowed before detach returns. Neither
         * a closed window nor a sticky error erases a valid physical fact.
         */
        if (!entry->state.ndi_reclaim_started ||
            !entry->state.recovery_dp_attempted || entry->state.recovery_dp_freed ||
            entry->state.ndi_completed_reclaim || !n->active ||
            !n->create.dp_attached || n->dp_detaching || n->dp_detach_submitted ||
            n->dp_freed || n->delete_pending || n->delete_submitted || n->delete_replied) {
            entry->state.blocked = true;
            n->blocked = true;
            if (!entry->state.recovery_error)
                entry->state.recovery_error = -EUCLEAN;
        } else {
            entry->state.recovery_dp_freed = true;
        }
        break;
    }
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    /* No access to context after publication. Unknown/freed tokens are ignored. */
}
static int mishare_runtime_recovery_error(struct mishare_runtime_owner *entry, int error)
{
    unsigned long flags;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    if (!entry->state.recovery_error)
        entry->state.recovery_error = error ? error : -EUCLEAN;
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    return -EUCLEAN;
}
/* Caller serializes all polls and retains the original native parents. No
 * DELETE or timer deinit is submitted here. A first DP detach is allowed only
 * after the ordinary DELETE reply; its submit and completion remain distinct.
 */
static int mishare_runtime_reclaim_ordinary_tail(struct mishare_runtime_owner **owner)
{
    struct mishare_runtime_owner *entry = *owner;
    struct mishare_ndi_reset_context_result result = {0};
    struct mishare_vdev_txn txn;
    struct vdev_mlme_obj *m;
    unsigned long flags;
    int ret;
    bool submit_dp;

    spin_lock_irqsave(&mishare_runtime_lock, flags);
    ret = mishare_runtime_rate_tail_check(entry);
    submit_dp = !ret && !entry->state.rate.tail_completed &&
                entry->state.recovery_window && !entry->state.ndi.dp_detaching;
    if (!ret && !submit_dp && !entry->state.rate.tail_completed &&
        (!entry->state.recovery_window || !entry->state.ndi.dp_freed))
        ret = -EINPROGRESS;
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    if (ret)
        return ret;
    if (entry->state.rate.tail_completed)
        return mishare_runtime_host_destroy(owner, true);
    if (mishare_events_snapshot(entry->events, &txn) ||
        txn.state != MISHARE_TXN_QUARANTINED || txn.serial ||
        txn.pending != MISHARE_TXN_NONE || txn.submitted || txn.replied)
        return mishare_runtime_recovery_error(entry, -EUCLEAN);
    m = wlan_vdev_mlme_get_cmpt_obj(entry->vdev);
    if (!m || m->vdev != entry->vdev)
        return mishare_runtime_recovery_error(entry, -EUCLEAN);
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    ret = mishare_runtime_rate_tail_check(entry);
    if (!ret && (!entry->state.recovery_window || entry->state.recovery_window_closed))
        ret = -ESHUTDOWN;
    if (!ret && submit_dp) {
        if (entry->state.ndi.dp_detaching || entry->state.rate.tail_dp_attempted)
            ret = -EUCLEAN;
        else {
            entry->state.rate.tail_dp_attempted = true;
            entry->state.ndi.dp_detaching = true;
            /* The ordinary native DELETE reply already completed deinit. */
            entry->state.ndi.create.timer_ready = false;
        }
    } else if (!ret)
        entry->state.rate.tail_attempted = true;
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    if (ret)
        return ret;
    if (submit_dp) {
        ret = mishare_ndi_reset_prepared_dp_detach(entry->vdev,
                    entry->state.ndi.create.dp_cookie, mishare_runtime_ndi_dp_freed, entry);
        if (ret)
            return mishare_runtime_recovery_error(entry, ret);
        spin_lock_irqsave(&mishare_runtime_lock, flags);
        entry->state.ndi.dp_detach_submitted = true;
        entry->state.ndi.create.stats_owned = false;
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return -EINPROGRESS; /* A real submit return precedes context release. */
    }
    ret = mishare_ndi_reset_context_finish(entry->vdev, entry->state.ndi.create.dp_cookie, &result);
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    if (result.wma_unbound)
        entry->state.ndi.wma_bound = false;
    if (result.legacy_released)
        entry->state.ndi.legacy_ready = false;
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    if (ret || !result.wma_unbound || !result.legacy_released)
        return mishare_runtime_recovery_error(entry, ret);
    m->mgmt.generic.type = WLAN_VDEV_MLME_TYPE_PASSTHRU;
    m->proto.generic.nss_2g = 0;
    m->proto.generic.nss_5g = 0;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    entry->state.ndi.active = false;
    entry->state.rate.ordinary_completed = true;
    entry->state.rate.tail_completed = true;
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    return mishare_runtime_host_destroy(owner, true);
}

/* Separate physical DP receipt for the peer-only SSR route. An inline
 * callback may precede submit return, but cannot bypass that return barrier. */
static void mishare_runtime_peer_reset_dp_freed(void *context)
{
    struct mishare_runtime_owner *entry;
    struct mishare_ndi_status *n;
    unsigned long flags;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    for (entry = mishare_runtime_owners; entry; entry = entry->next) {
        if (entry != context)
            continue;
        n = &entry->state.ndi;
        if (!entry->state.rate.peer_reset_admitted ||
            !entry->state.rate.peer_timer_released || !entry->state.rate.peer_dp_attempted ||
            entry->state.quiesced != MISHARE_QUIESCE_SSR ||
            !n->active || !n->dp_detaching || n->dp_freed ||
            !n->peer_delete_submitted || !n->peer_delete_replied ||
            n->delete_pending || n->delete_submitted || n->delete_replied) {
            n->blocked = true;
            if (!n->completion_error)
                n->completion_error = -EUCLEAN;
        } else if (!n->completion_error)
            n->dp_freed = true;
        break;
    }
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
}

/* Native parents remain held by the serialized caller. No PE/peer/VDEV
 * firmware command is sent: ordinary PE/peer ACKs and physical peer absence
 * precede native DP detach, then physical DP free precedes context finish. */
static int mishare_runtime_reclaim_peer_reset(struct mishare_runtime_owner **owner)
{
    struct mishare_runtime_owner *entry = *owner;
    struct mishare_ndi_reset_context_result result = {0};
    struct mishare_vdev_txn txn;
    struct vdev_mlme_obj *m;
    unsigned long flags;
    bool timer, dp;
    int ret;

    spin_lock_irqsave(&mishare_runtime_lock, flags);
    ret = mishare_runtime_rate_peer_reset_check(entry);
    timer = !entry->state.rate.peer_timer_released;
    dp = !entry->state.rate.peer_dp_attempted;
    if (!ret && !entry->state.rate.peer_reset_completed &&
        (!entry->state.recovery_window || (!timer && !dp && !entry->state.ndi.dp_freed)))
        ret = -EINPROGRESS;
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    if (ret)
        return ret;
    if (entry->state.rate.peer_reset_completed)
        return mishare_runtime_host_destroy(owner, true);
    if (mishare_events_snapshot(entry->events, &txn) ||
        txn.state != MISHARE_TXN_QUARANTINED || txn.serial ||
        txn.pending != MISHARE_TXN_NONE || txn.submitted || txn.replied)
        return mishare_runtime_recovery_error(entry, -EUCLEAN);
    m = wlan_vdev_mlme_get_cmpt_obj(entry->vdev);
    if (!m || m->vdev != entry->vdev)
        return mishare_runtime_recovery_error(entry, -EUCLEAN);
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    ret = mishare_runtime_rate_peer_reset_check(entry);
    if (!ret && (!entry->state.recovery_window || entry->state.recovery_window_closed))
        ret = -ESHUTDOWN;
    if (!ret) {
        entry->state.rate.peer_reset_admitted = true;
        if (timer)
            entry->state.rate.peer_timer_attempted = true;
        else if (dp) {
            entry->state.rate.peer_dp_attempted = true;
            entry->state.ndi.dp_detaching = true;
        } else
            entry->state.rate.peer_finish_attempted = true;
    }
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    if (ret)
        return ret;
    if (timer) {
        ret = mishare_ndi_reset_prepared_timer_deinit(entry->vdev);
        if (ret)
            return mishare_runtime_recovery_error(entry, ret);
        spin_lock_irqsave(&mishare_runtime_lock, flags);
        entry->state.rate.peer_timer_released = true;
        entry->state.ndi.create.timer_ready = false;
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return -EINPROGRESS; /* The native timer helper returned successfully. */
    }
    if (dp) {
        ret = mishare_ndi_reset_prepared_dp_detach(entry->vdev,
                    entry->state.ndi.create.dp_cookie, mishare_runtime_peer_reset_dp_freed, entry);
        if (ret)
            return mishare_runtime_recovery_error(entry, ret);
        spin_lock_irqsave(&mishare_runtime_lock, flags);
        entry->state.ndi.dp_detach_submitted = true;
        entry->state.ndi.create.stats_owned = false;
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return -EINPROGRESS; /* Peer-reset DP submit must return before finish. */
    }
    ret = mishare_ndi_reset_context_finish(entry->vdev, entry->state.ndi.create.dp_cookie, &result);
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    if (result.wma_unbound)
        entry->state.ndi.wma_bound = false;
    if (result.legacy_released)
        entry->state.ndi.legacy_ready = false;
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    if (ret || !result.wma_unbound || !result.legacy_released)
        return mishare_runtime_recovery_error(entry, ret);
    m->mgmt.generic.type = WLAN_VDEV_MLME_TYPE_PASSTHRU;
    m->proto.generic.nss_2g = 0;
    m->proto.generic.nss_5g = 0;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    entry->state.ndi.active = false;
    entry->state.ndi.peer_created = false;
    entry->state.rate.peer_reset_completed = true;
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    return mishare_runtime_host_destroy(owner, true);
}

int mishare_runtime_reclaim_ndi(struct mishare_runtime_owner **owner)
{
    struct mishare_runtime_owner *entry;
    struct mishare_vdev_txn txn;
    struct vdev_mlme_obj *m;
    unsigned long flags;
    bool started, timer_done, dp_attempted, dp_freed, context_live;
    int ret = 0;
    if (!owner)
        return -EINVAL;
    entry = *owner;
    if (!entry)
        return 0;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    if (entry->state.rate.peer_reset_armed || entry->state.rate.late_peer_reply) {
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return mishare_runtime_reclaim_peer_reset(owner);
    }
    if (entry->state.rate.ordinary_admitted && entry->state.ndi.delete_replied &&
        !entry->state.rate.ordinary_completed) {
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return mishare_runtime_reclaim_ordinary_tail(owner);
    }
    if (entry->state.rate.tail_completed) {
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return mishare_runtime_reclaim_ordinary_tail(owner);
    }
    ret = mishare_runtime_rate_reset_check(entry);
    if (ret) {
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return ret;
    }

    if (entry->state.work_error || entry->state.recovery_error || entry->state.reclaim_error ||
        entry->state.ndi.completion_error ||
        entry->state.quiesced != MISHARE_QUIESCE_SSR || entry->state.host_reclaim)
        ret = -EUCLEAN;
    else if (entry->state.ndi_reclaim_ready && entry->state.draining && !entry->vdev)
        ret = 1; /* Only final-free bookkeeping remains; no native handle access. */
    else if (entry->state.recovery_window_closed)
        ret = -ESHUTDOWN;
    else if (!entry->state.mc_drained || entry->state.work_pending || entry->state.work_users)
        ret = -EINPROGRESS;
    else if (mishare_runtime_ndi_completed_candidate(entry))
        ret = entry->state.recovery_window ? 2 : -EINPROGRESS;
    else if (!entry->state.ndi_reclaim_started && !mishare_runtime_ndi_recovery_candidate(entry))
        ret = -EUCLEAN;
    else if (!entry->state.recovery_window)
        ret = -EINPROGRESS;
    started = entry->state.ndi_reclaim_started;
    timer_done = entry->state.recovery_timer_released;
    dp_attempted = entry->state.recovery_dp_attempted;
    dp_freed = entry->state.recovery_dp_freed;
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    if (ret == 1)
        return mishare_runtime_host_destroy(owner, true);
    if (ret && ret != 2)
        return ret;
    if (!started && ret != 2 && entry->state.ndi.legacy_ready) {
        struct mishare_ndi_reset_context_result result = {0};
        u32 pe_freq = entry->state.ndi.channel_prepared ? entry->state.ndi.channel_freq : 0;

        if (mishare_events_snapshot(entry->events, &txn) ||
            !mishare_runtime_recovery_txn_valid(entry, &txn))
            return mishare_runtime_recovery_error(entry, -EUCLEAN);
        ret = mishare_ndi_reset_context_check(entry->vdev,
                                               entry->state.ndi.create.dp_cookie);
        if (ret)
            return mishare_runtime_recovery_error(entry, ret);
        if (entry->state.ndi.pe_ready) {
            ret = mishare_ndi_reset_pe_check(entry->vdev, entry, entry->pe_cookie,
                                             entry->state.ndi.create.dp_cookie, pe_freq);
            if (ret)
                return mishare_runtime_recovery_error(entry, ret);
        }
        if (entry->radio && !entry->state.recovery_down_observed) {
            struct mishare_radio_status radio_observed = {0};

            ret = mishare_radio_ssr_cancel_check(entry->radio, entry->vdev, entry->events,
                                                  entry, entry->pe_cookie, pe_freq);
            if (!ret)
                ret = mishare_radio_snapshot(entry->radio, &radio_observed);
            if (!ret && (radio_observed.ssr_start_init_rejected != entry->state.recovery_radio_init_rejected ||
                         radio_observed.ssr_start_sm_entry_aborted != entry->state.recovery_radio_sm_entry_aborted ||
                         radio_observed.ssr_start_prepared_aborted != entry->state.recovery_radio_prepared_aborted ||
                         radio_observed.ssr_start_body_aborted != entry->state.recovery_radio_start_aborted ||
                         radio_observed.ssr_start_callback_refused != entry->state.recovery_radio_start_refused ||
                         radio_observed.error != (entry->state.ndi.radio_submit_error ?
                                                   entry->state.ndi.radio_submit_error : -ESHUTDOWN)))
                ret = -EUCLEAN;
            if (ret)
                return mishare_runtime_recovery_error(entry, ret);
        }
        spin_lock_irqsave(&mishare_runtime_lock, flags);
        if (entry->state.rate.receipt.attempted) {
            if (!entry->state.recovery_window || entry->state.recovery_window_closed ||
                mishare_runtime_rate_reset_check(entry)) {
                spin_unlock_irqrestore(&mishare_runtime_lock, flags);
                return mishare_runtime_recovery_error(entry, -EUCLEAN);
            }
            entry->state.rate.reset_admitted = true;
        }
        entry->state.recovery_timer_attempted = true;
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        if (entry->state.recovery_down_observed) {
            struct mishare_radio_status last = {0};

            ret = mishare_radio_snapshot(entry->radio, &last);
            if (!ret)
                ret = mishare_radio_fenced_down_release(&entry->radio, entry->vdev, entry->events,
                                                        entry, entry->pe_cookie, pe_freq, &last);
            spin_lock_irqsave(&mishare_runtime_lock, flags);
            entry->state.radio = last;
            entry->state.recovery_timer_attempted = last.down_retire_timer_attempted;
            entry->state.recovery_timer_released = last.down_retire_timer_released;
            if (last.down_retire_timer_released)
                entry->state.ndi.create.timer_ready = false;
            entry->state.recovery_down_released = !ret && !entry->radio && last.down_retired;
            if (!ret && !mishare_runtime_down_origin_valid(entry))
                ret = -EUCLEAN;
            spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        } else
            ret = mishare_ndi_reset_prepared_timer_deinit(entry->vdev);
        if (ret)
            return mishare_runtime_recovery_error(entry, ret);
        spin_lock_irqsave(&mishare_runtime_lock, flags);
        entry->state.recovery_timer_released = true;
        entry->state.ndi.create.timer_ready = false;
        if (entry->state.ndi.completion_error)
            ret = -EUCLEAN;
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        timer_done = true;
        if (ret)
            return mishare_runtime_recovery_error(entry, ret);
        if (entry->radio && !entry->state.recovery_down_observed) {
            struct mishare_radio_status last = {0};

            ret = mishare_radio_ssr_cancel_release(&entry->radio, entry->vdev, entry->events,
                                                    entry, entry->pe_cookie, pe_freq, &last);
            if (ret || entry->radio || !last.ssr_cancelled_before_start ||
                last.ssr_start_submit_error != entry->state.ndi.radio_submit_error ||
                last.ssr_start_callback_refused != entry->state.recovery_radio_start_refused ||
                last.ssr_start_body_aborted != entry->state.recovery_radio_start_aborted ||
                last.ssr_start_prepared_aborted != entry->state.recovery_radio_prepared_aborted ||
                last.ssr_start_sm_entry_aborted != entry->state.recovery_radio_sm_entry_aborted ||
                last.ssr_start_init_rejected != entry->state.recovery_radio_init_rejected)
                return mishare_runtime_recovery_error(entry, ret);
            spin_lock_irqsave(&mishare_runtime_lock, flags);
            entry->state.radio = last;
            entry->state.recovery_radio_released = true;
            spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        }
        if (entry->state.ndi.pe_ready) {
            bool released = false;

            spin_lock_irqsave(&mishare_runtime_lock, flags);
            entry->state.recovery_pe_attempted = true;
            spin_unlock_irqrestore(&mishare_runtime_lock, flags);
            ret = mishare_ndi_reset_pe_release(entry->vdev, entry, entry->pe_cookie,
                                               entry->state.ndi.create.dp_cookie,
                                               pe_freq, &released);
            spin_lock_irqsave(&mishare_runtime_lock, flags);
            entry->state.recovery_pe_released = released;
            if (released) {
                entry->state.ndi.pe_ready = false;
                entry->pe_cookie = 0;
            }
            spin_unlock_irqrestore(&mishare_runtime_lock, flags);
            if (ret || !released)
                return mishare_runtime_recovery_error(entry, ret);
        }
        spin_lock_irqsave(&mishare_runtime_lock, flags);
        entry->state.recovery_context_attempted = true;
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        ret = mishare_ndi_reset_context_release(entry->vdev,
                                                 entry->state.ndi.create.dp_cookie,
                                                 &result);
        spin_lock_irqsave(&mishare_runtime_lock, flags);
        entry->state.recovery_peer_released = result.peer_released;
        if (result.peer_released)
            entry->state.ndi.peer_created = false;
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        if (ret || !entry->state.recovery_peer_released)
            return mishare_runtime_recovery_error(entry, ret);
    }
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    context_live = entry->state.recovery_context_attempted &&
                   entry->state.recovery_peer_released &&
                   !entry->state.recovery_context_released;
    if (context_live && (!entry->state.ndi.legacy_ready ||
        !entry->state.ndi.wma_bound || entry->state.ndi.peer_created))
        ret = -EUCLEAN;
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    if (ret && ret != 2)
        return mishare_runtime_recovery_error(entry, ret);
    m = wlan_vdev_mlme_get_cmpt_obj(entry->vdev);
    if (!m || m->vdev != entry->vdev || (!!m->ext_vdev_ptr != context_live) ||
        wlan_vdev_mlme_get_opmode(entry->vdev) != QDF_PASSTHRU_MODE ||
        m->mgmt.generic.type != WLAN_VDEV_MLME_TYPE_NDI || m->mgmt.generic.subtype ||
        wlan_vdev_mlme_get_state(entry->vdev) != WLAN_VDEV_S_INIT)
        return mishare_runtime_recovery_error(entry, -EUCLEAN);
    if (ret == 2) {
        if (mishare_events_snapshot(entry->events, &txn) ||
            !mishare_runtime_recovery_txn_valid(entry, &txn))
            return mishare_runtime_recovery_error(entry, -EUCLEAN);
        spin_lock_irqsave(&mishare_runtime_lock, flags);
        if (!entry->state.recovery_window ||
            !mishare_runtime_ndi_completed_candidate(entry)) {
            ret = entry->state.recovery_window_closed ? -ESHUTDOWN : -EUCLEAN;
            spin_unlock_irqrestore(&mishare_runtime_lock, flags);
            return ret;
        }
        m->mgmt.generic.type = WLAN_VDEV_MLME_TYPE_PASSTHRU;
        m->proto.generic.nss_2g = 0;
        m->proto.generic.nss_5g = 0;
        entry->state.ndi.create.dp_attached = false;
        entry->state.ndi.active = false;
        entry->state.ndi_reclaim_started = true;
        entry->state.ndi_reclaim_ready = true;
        entry->state.ndi_completed_reclaim = true;
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return mishare_runtime_host_destroy(owner, true);
    }
    if (!started) {
        if (mishare_events_snapshot(entry->events, &txn) ||
            !mishare_runtime_recovery_txn_valid(entry, &txn))
            return mishare_runtime_recovery_error(entry, -EUCLEAN);
        spin_lock_irqsave(&mishare_runtime_lock, flags);
        entry->state.ndi_reclaim_started = true;
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        if (!timer_done) {
            spin_lock_irqsave(&mishare_runtime_lock, flags);
            entry->state.recovery_timer_attempted = true;
            spin_unlock_irqrestore(&mishare_runtime_lock, flags);
            ret = mishare_ndi_recovery_timer_deinit(entry->vdev);
            if (ret)
                return mishare_runtime_recovery_error(entry, ret);
            spin_lock_irqsave(&mishare_runtime_lock, flags);
            entry->state.recovery_timer_released = true;
            entry->state.ndi.create.timer_ready = false;
            spin_unlock_irqrestore(&mishare_runtime_lock, flags);
            timer_done = true;
        }
    }
    if (!timer_done)
        return mishare_runtime_recovery_error(entry, -EUCLEAN);
    if (!dp_attempted) {
        spin_lock_irqsave(&mishare_runtime_lock, flags);
        entry->state.recovery_dp_attempted = true;
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        ret = context_live ?
              mishare_ndi_reset_prepared_dp_detach(entry->vdev, entry->state.ndi.create.dp_cookie,
                                                    mishare_runtime_recovery_dp_freed, entry) :
              mishare_ndi_recovery_dp_detach(entry->vdev, entry->state.ndi.create.dp_cookie,
                                              mishare_runtime_recovery_dp_freed, entry);
        if (ret)
            return mishare_runtime_recovery_error(entry, ret);
        spin_lock_irqsave(&mishare_runtime_lock, flags);
        entry->state.ndi.create.stats_owned = false; /* Native detach resets stats ID. */
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return -EINPROGRESS; /* Submit return must precede final host deletion. */
    }
    if (!dp_freed)
        return -EINPROGRESS;
    if (context_live) {
        struct mishare_ndi_reset_context_result result = {0};

        spin_lock_irqsave(&mishare_runtime_lock, flags);
        if (entry->state.recovery_context_finish_attempted) {
            spin_unlock_irqrestore(&mishare_runtime_lock, flags);
            return mishare_runtime_recovery_error(entry, -EUCLEAN);
        }
        entry->state.recovery_context_finish_attempted = true;
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        ret = mishare_ndi_reset_context_finish(entry->vdev,
                                                entry->state.ndi.create.dp_cookie, &result);
        spin_lock_irqsave(&mishare_runtime_lock, flags);
        if (result.wma_unbound)
            entry->state.ndi.wma_bound = false;
        if (result.legacy_released)
            entry->state.ndi.legacy_ready = false;
        entry->state.recovery_context_released = !ret && result.wma_unbound && result.legacy_released;
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        if (ret || !entry->state.recovery_context_released)
            return mishare_runtime_recovery_error(entry, ret);
    }
    /* INIT was observed, never manufactured. No DELETE ACK flags are written. */
    m->mgmt.generic.type = WLAN_VDEV_MLME_TYPE_PASSTHRU;
    m->proto.generic.nss_2g = 0;
    m->proto.generic.nss_5g = 0;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    entry->state.ndi.create.dp_attached = false;
    entry->state.ndi.active = false;
    entry->state.ndi_reclaim_ready = true;
    if (entry->state.rate.receipt.attempted) {
        if (!entry->state.rate.reset_admitted || !entry->state.recovery_timer_released ||
            !entry->state.recovery_pe_released || !entry->state.recovery_context_released ||
            !entry->state.recovery_dp_freed)
            ret = -EUCLEAN;
        else
            entry->state.rate.reset_completed = true;
    }
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    if (ret)
        return mishare_runtime_recovery_error(entry, ret);
    return mishare_runtime_host_destroy(owner, true);
}

/* Registry lock held. Pure metadata only: no native pointer is dereferenced. */
static bool mishare_runtime_final_shape_valid(struct mishare_runtime_owner *entry)
{
    struct mishare_ndi_status *n = &entry->state.ndi;

    if (mishare_runtime_rate_final_check(entry))
        return false;
    return (!(entry->state.recovery_down_observed || entry->state.recovery_down_released) ||
            mishare_runtime_down_completion_valid(entry)) &&
           ((!entry->state.recovery_radio_start_flushed && !entry->state.recovery_radio_start_refused &&
             !entry->state.recovery_radio_start_aborted && !entry->state.recovery_radio_prepared_aborted &&
           !entry->state.recovery_radio_sm_entry_aborted && !entry->state.recovery_radio_init_rejected &&
           !entry->state.recovery_radio_released) ||
            (mishare_runtime_radio_origin_valid(entry) &&
             entry->state.recovery_radio_released &&
             n->radio_requested && entry->state.radio.ssr_cancelled_before_start &&
             entry->state.radio.phase == MISHARE_RADIO_BLOCKED &&
             entry->state.radio.ssr_start_submit_error == n->radio_submit_error &&
             entry->state.radio.ssr_start_callback_refused == entry->state.recovery_radio_start_refused &&
             entry->state.radio.ssr_start_body_aborted == entry->state.recovery_radio_start_aborted &&
             entry->state.radio.ssr_start_prepared_aborted == entry->state.recovery_radio_prepared_aborted &&
             entry->state.radio.ssr_start_sm_entry_aborted == entry->state.recovery_radio_sm_entry_aborted &&
             entry->state.radio.ssr_start_init_rejected == entry->state.recovery_radio_init_rejected &&
             entry->state.radio.error == (n->radio_submit_error ? n->radio_submit_error : -ESHUTDOWN) &&
             !entry->state.radio.pending &&
             !entry->state.radio.users && !entry->state.radio.start_attempted &&
             !entry->state.radio.stop_attempted && !entry->state.radio.host_up &&
             !entry->state.radio.down_attempted && !entry->state.radio.down_accepted)) &&
           ((!entry->state.recovery_pe_attempted && !entry->state.recovery_pe_released) ||
            (entry->state.recovery_pe_attempted && entry->state.recovery_pe_released &&
             entry->state.recovery_context_released && n->pe_requested &&
             n->pe_submitted && n->pe_completed && !n->pe_delete_requested &&
             !n->pe_delete_submitted && !n->pe_delete_completed)) &&
           !n->pe_ready &&
           (!entry->state.recovery_context_attempted ||
            (entry->state.recovery_peer_released && entry->state.recovery_context_finish_attempted &&
             entry->state.recovery_context_released)) &&
           entry->state.host_delete_accepted && entry->state.draining &&
           entry->state.allocated && !entry->vdev && !entry->referenced &&
           !entry->events && !entry->radio && !entry->pe_cookie && !n->active &&
           !n->legacy_ready && !n->wma_bound && !n->create.timer_ready &&
           !n->create.stats_owned;
}

int mishare_runtime_reclaim_final(struct mishare_runtime_owner **owner)
{
    struct mishare_runtime_owner *entry, **link;
    struct mishare_ndi_status *n;
    unsigned long flags;
    int ret = 0;

    if (!owner)
        return -EINVAL;
    if (!*owner)
        return 0;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    for (link = &mishare_runtime_owners; *link && *link != *owner;
         link = &(*link)->next)
        ;
    entry = *link;
    if (!entry) {
        ret = -ENOENT;
        goto final_unlock;
    }
    ret = mishare_runtime_rate_final_check(entry);
    if (ret)
        goto final_unlock;
    n = &entry->state.ndi;
    if (entry->state.quiesced != MISHARE_QUIESCE_SSR ||
        entry->state.work_error || entry->state.reclaim_error ||
        entry->state.recovery_error || n->completion_error)
        ret = -EUCLEAN;
    else if (!mishare_runtime_final_shape_valid(entry))
        ret = -EUCLEAN;
    else if (!entry->state.mc_drained || entry->state.work_pending ||
             entry->state.work_users || !entry->state.freed)
        ret = -EINPROGRESS;
    if (ret)
        goto final_unlock;
    *link = entry->next;
    *owner = NULL;
final_unlock:
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    if (!ret) {
        kfree(entry);
        module_put(THIS_MODULE);
    }
    return ret;
}

int mishare_runtime_reclaim_batch(struct wlan_objmgr_psoc *psoc,
                                  struct mishare_runtime_reclaim_item *items,
                                  unsigned int count)
{
    struct mishare_runtime_owner *entry;
    unsigned long flags;
    unsigned int i, j;
    bool found, ndi, final_only;
    int ret = 0, error = 0;

    if (!psoc || (count && !items))
        return -EINVAL;
    if (count > MISHARE_RUNTIME_RECLAIM_BATCH_MAX)
        return -E2BIG;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    /* Opaque handles are compared before any dereference. */
    for (i = 0; i < count; i++) {
        if (!items[i].owner)
            continue;
        for (j = 0; j < i; j++) {
            if (items[j].owner == items[i].owner) {
                ret = -EEXIST;
                goto unlock;
            }
        }
        for (entry = mishare_runtime_owners; entry; entry = entry->next)
            if (entry == items[i].owner)
                break;
        if (!entry) {
            ret = -ENOENT;
            goto unlock;
        }
        if (entry->psoc != psoc) {
            ret = -EXDEV;
            goto unlock;
        }
    }
    for (entry = mishare_runtime_owners; entry; entry = entry->next) {
        if (entry->psoc != psoc)
            continue;
        found = false;
        for (i = 0; i < count; i++)
            if (items[i].owner == entry)
                found = true;
        if (!found) {
            ret = -EBUSY;
            goto unlock;
        }
    }
    /* Validate complete coverage before policy/accounting. A waiting owner
     * must not hide an omitted owner or a fatal error later in this list.
     */
    for (entry = mishare_runtime_owners; entry; entry = entry->next) {
        if (entry->psoc != psoc)
            continue;
        {
            int rate_ret = entry->state.host_delete_accepted ?
                           mishare_runtime_rate_final_check(entry) :
                           (entry->state.rate.peer_reset_armed || entry->state.rate.late_peer_reply) ?
                           mishare_runtime_rate_peer_reset_check(entry) :
                           entry->state.rate.ordinary_admitted && entry->state.ndi.delete_replied ?
                           mishare_runtime_rate_tail_check(entry) :
                           mishare_runtime_rate_reset_check(entry);
            if (rate_ret && rate_ret != -EINPROGRESS) {
                ret = rate_ret;
                goto unlock;
            }
            if (rate_ret)
                ret = rate_ret;
        }
        if (entry->state.quiesced != MISHARE_QUIESCE_SSR) {
            ret = -ESHUTDOWN;
            goto unlock;
        }
        if (entry->state.work_error || entry->state.reclaim_error ||
            entry->state.ndi.completion_error ||
            entry->state.recovery_error) {
            ret = -EUCLEAN;
            goto unlock;
        }
        /* An accepted delete selects metadata-only retirement. Reject
         * impossible retained handles before ANY item performs native work,
         * even if another owner is still waiting for MC or final-free.
         */
        if (entry->state.host_delete_accepted &&
            !mishare_runtime_final_shape_valid(entry)) {
            ret = -EUCLEAN;
            goto unlock;
        }
        if (!entry->state.mc_drained || entry->state.work_pending ||
            entry->state.work_users)
            ret = -EINPROGRESS;
    }
unlock:
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    if (ret)
        return ret;

    /* No registry lock crosses native timer/DP/object-manager operations.
     * Caller serialization keeps each admitted handle stable between polls.
     */
    for (i = 0; i < count; i++) {
        entry = items[i].owner;
        if (!entry) {
            items[i].result = 0;
            continue;
        }
        spin_lock_irqsave(&mishare_runtime_lock, flags);
        final_only = entry->state.host_delete_accepted;
        ndi = entry->state.ndi.active || entry->state.ndi.create.wire_attempted ||
              entry->state.ndi_reclaim_started || entry->state.ndi_reclaim_ready;
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        ret = final_only ? mishare_runtime_reclaim_final(&items[i].owner) :
              ndi ? mishare_runtime_reclaim_ndi(&items[i].owner) :
                    mishare_runtime_reclaim_host(&items[i].owner);
        if (!ret && items[i].owner)
            ret = -EUCLEAN;
        items[i].result = ret;
        if (ret && ret != -EINPROGRESS && !error)
            error = ret;
    }
    if (error)
        return error;
    /* Do not infer global completion from the caller's cleared slots alone. */
    ret = 0;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    for (entry = mishare_runtime_owners; entry; entry = entry->next) {
        if (entry->psoc == psoc) {
            ret = -EINPROGRESS;
            break;
        }
    }
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    return ret;
}

int mishare_runtime_create(struct wlan_objmgr_pdev *pdev, const u8 *mac,
                           void *osif, struct wireless_dev *wdev,
                           struct mishare_runtime_owner **owner)
{
    struct wlan_vdev_create_params params = {0};
    struct mishare_runtime_owner *entry, *other;
    struct wlan_objmgr_vdev *vdev;
    struct vdev_mlme_obj *mlme;
    struct wlan_objmgr_psoc *psoc;
    struct vdev_osif_priv *priv;
    unsigned long flags;
    unsigned int id;
    int ret = -EIO, cleanup;

    if (!owner || !pdev || !mac || !is_valid_ether_addr(mac) || !osif || !wdev)
        return -EINVAL;
    if (*owner)
        return -EBUSY;
    psoc = wlan_pdev_get_psoc(pdev);
    if (!psoc)
        return -ENODEV;
    if (!mishare_runtime_platform_available(psoc))
        return -ESHUTDOWN;
    /* Standalone owners need their own module reference: a host lease cannot
     * cover asynchronous runtime/final-free retention after host handoff.
     */
    if (!try_module_get(THIS_MODULE))
        return -ESHUTDOWN;
    entry = kzalloc(sizeof(*entry), GFP_KERNEL);
    if (!entry) {
        module_put(THIS_MODULE);
        return -ENOMEM;
    }
    entry->psoc = psoc;
    ether_addr_copy(entry->mac, mac);
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    for (other = mishare_runtime_owners; other; other = other->next) {
        if (other->psoc == psoc && other->state.quiesced) {
            spin_unlock_irqrestore(&mishare_runtime_lock, flags);
            kfree(entry);
            module_put(THIS_MODULE);
            return -EUCLEAN;
        }
        if (other->psoc == psoc && ether_addr_equal(other->mac, mac)) {
            spin_unlock_irqrestore(&mishare_runtime_lock, flags);
            kfree(entry);
            module_put(THIS_MODULE);
            return -EEXIST;
        }
    }
    entry->next = mishare_runtime_owners;
    mishare_runtime_owners = entry;
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    *owner = entry;
    params.opmode = QDF_PASSTHRU_MODE;
    params.size_vdev_priv = sizeof(struct vdev_osif_priv);
    params.legacy_osif = osif;
    ether_addr_copy(params.macaddr, mac);
    /* Zero MLD/mat/flags: never claim an MLO link or use SME post-setup. */
    vdev = wlan_objmgr_vdev_obj_create(pdev, &params);
    if (!vdev) {
        spin_lock_irqsave(&mishare_runtime_lock, flags);
        entry->state.draining = true; /* native NULL paths already delete */
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        goto failed;
    }
    entry->vdev = vdev;
    if (!entry->state.allocated || entry->cookie != (unsigned long)vdev) {
        spin_lock_irqsave(&mishare_runtime_lock, flags);
        entry->state.blocked = true;
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        goto failed;
    }
    if (wlan_objmgr_vdev_try_get_ref(vdev, WLAN_HDD_ID_OBJ_MGR) !=
        QDF_STATUS_SUCCESS)
        goto failed;
    entry->referenced = true;
    /* Reject partial/failed component states even if native aggregation did
     * not classify a status (e.g. E_INVAL) as a construction failure.
     */
    for (id = 0; id < WLAN_UMAC_MAX_COMPONENTS; id++) {
        if (vdev->obj_status[id] != QDF_STATUS_SUCCESS &&
            vdev->obj_status[id] != QDF_STATUS_COMP_DISABLED)
            goto failed;
    }
    mlme = wlan_vdev_mlme_get_cmpt_obj(vdev);
    priv = wlan_vdev_get_ospriv(vdev);
    if (!entry->state.allocated || entry->cookie != (unsigned long)vdev ||
        !mlme || !priv || mlme->vdev != vdev || mlme->ext_vdev_ptr ||
        mlme->mgmt.generic.type != WLAN_VDEV_MLME_TYPE_PASSTHRU ||
        mlme->mgmt.generic.subtype)
        goto failed;
    priv->wdev = wdev;
    ret = mishare_events_bind(vdev, &entry->events);
    if (!ret)
        return 0;
failed:
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    entry->state.create_error = ret;
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    cleanup = mishare_runtime_destroy(owner);
    return cleanup ? cleanup : ret;
}


bool mishare_runtime_ndi_delete_owned(struct wlan_objmgr_psoc *psoc, u8 id)
{
    struct mishare_runtime_owner *entry;
    unsigned long flags;
    bool owned = false;

    spin_lock_irqsave(&mishare_runtime_lock, flags);
    for (entry = mishare_runtime_owners; entry; entry = entry->next) {
        if (entry->psoc == psoc && entry->state.ndi.active && entry->vdev &&
            wlan_vdev_get_id(entry->vdev) == id) {
            owned = true;
            break;
        }
    }
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    return owned;
}

void mishare_runtime_ndi_delete_event(struct wlan_objmgr_psoc *psoc, u8 id,
                                      bool firmware)
{
    struct mishare_runtime_owner *entry;
    struct mishare_ndi_status *ndi;
    unsigned long flags;

    spin_lock_irqsave(&mishare_runtime_lock, flags);
    for (entry = mishare_runtime_owners; entry; entry = entry->next) {
        ndi = &entry->state.ndi;
        if (entry->psoc != psoc || !ndi->active || !entry->vdev ||
            wlan_vdev_get_id(entry->vdev) != id)
            continue;
        if (!firmware || !ndi->delete_pending || ndi->delete_replied) {
            ndi->blocked = true;
            if (!ndi->completion_error)
                ndi->completion_error = -EUCLEAN;
        } else if (!ndi->blocked)
            ndi->delete_replied = true;
        else if (entry->state.rate.late_delete_armed &&
                 entry->state.quiesced == MISHARE_QUIESCE_SSR &&
                 mishare_runtime_rate_delete_inflight(entry)) {
            /* Native handler already completed timer/PM cleanup. Preserve
             * the fence and errors; only record this exact physical origin.
             */
            ndi->delete_replied = true;
            entry->state.rate.late_delete_reply = true;
        }
        break;
    }
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
}

/* Host MLME metadata, equivalent to upstream's BSSID setter. This must run
 * before firmware CREATE/PE on this owner; it does not change PE's MAC key or
 * send firmware commands. Caller serializes polls and retains native parents. */
int mishare_runtime_bssid_bind(struct mishare_runtime_owner *entry, const u8 *bssid)
{
    struct mishare_runtime_bssid_status *b;
    struct vdev_mlme_obj *m;
    unsigned long flags;
    bool write;
    int ret = 0;

    if (!entry || !bssid)
        return -EINVAL;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    b = &entry->state.bssid;
    if (entry->state.quiesced || entry->state.draining || entry->state.freed)
        ret = -ESHUTDOWN;
    else if (entry->state.blocked || entry->state.ndi.blocked || entry->state.work_error ||
             entry->state.ndi.completion_error || b->error)
        ret = b->error ? b->error : -EUCLEAN;
    else if (!entry->vdev || !entry->referenced || !entry->events ||
             entry->cookie != (unsigned long)entry->vdev || !entry->state.allocated)
        ret = -EUCLEAN;
    else if (b->requested && memcmp(b->value, bssid, ETH_ALEN))
        ret = -EBUSY;
    else if (entry->state.work_pending || entry->state.work_users)
        ret = -EINPROGRESS;
    else if (!b->requested && (entry->state.ndi.active || entry->state.ndi.create.wire_attempted ||
             entry->state.ndi.pe_requested || entry->state.rate.requested || entry->radio))
        ret = -EBUSY;
    else if (b->requested && !b->applied)
        ret = -EUCLEAN;
    write = !b->requested;
    if (!ret && write) {
        b->requested = true;
        memcpy(b->value, bssid, ETH_ALEN);
    }
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    if (ret)
        return ret;
    m = wlan_vdev_mlme_get_cmpt_obj(entry->vdev);
    if (!m || m->vdev != entry->vdev || m->mgmt.generic.subtype ||
        m->mgmt.generic.type != (entry->state.ndi.active ?
            WLAN_VDEV_MLME_TYPE_NDI : WLAN_VDEV_MLME_TYPE_PASSTHRU) ||
        wlan_vdev_mlme_get_opmode(entry->vdev) != QDF_PASSTHRU_MODE ||
        (write && (m->ext_vdev_ptr || m->mgmt.generic.type != WLAN_VDEV_MLME_TYPE_PASSTHRU ||
                   wlan_vdev_mlme_get_state(entry->vdev) != WLAN_VDEV_S_INIT)))
        ret = -EUCLEAN;
    else {
        if (write)
            memcpy(m->mgmt.generic.bssid, b->value, ETH_ALEN);
        if (memcmp(m->mgmt.generic.bssid, b->value, ETH_ALEN))
            ret = -EUCLEAN;
    }
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    if (ret) {
        if (!b->error)
            b->error = ret;
        entry->state.blocked = true;
        entry->state.ndi.blocked = true;
    } else
        b->applied = true;
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    return ret;
}

int mishare_runtime_ndi_create(struct mishare_runtime_owner *entry,
                               u8 nss_2g, u8 nss_5g)
{
    struct vdev_mlme_obj *mlme;
    struct mishare_ndi_status *ndi;
    unsigned long flags;
    int ret;

    if (!entry || !nss_2g || nss_2g > 2 || !nss_5g || nss_5g > 2)
        return -EINVAL;
    /* Owner-handle calls are serialized by the caller; only notifications
     * run concurrently. No lock is held across native allocations/transports.
     */
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    ndi = &entry->state.ndi;
    if (entry->state.blocked || ndi->blocked) {
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return -EUCLEAN;
    }
    if (!entry->vdev || !entry->referenced || !entry->events ||
        entry->state.draining || ndi->active || ndi->create.wire_attempted) {
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return -EBUSY;
    }
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    mlme = wlan_vdev_mlme_get_cmpt_obj(entry->vdev);
    if (!mlme || mlme->vdev != entry->vdev || mlme->ext_vdev_ptr ||
        mlme->mgmt.generic.type != WLAN_VDEV_MLME_TYPE_PASSTHRU ||
        mlme->mgmt.generic.subtype || mlme->proto.generic.nss_2g ||
        mlme->proto.generic.nss_5g)
        return -EINVAL;
    mlme->mgmt.generic.type = WLAN_VDEV_MLME_TYPE_NDI;
    mlme->proto.generic.nss_2g = nss_2g;
    mlme->proto.generic.nss_5g = nss_5g;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    ndi->active = true;
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    ret = mishare_ndi_native_create(mlme, &ndi->create);
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    ndi->create_error = ret;
    if (ret && !ndi->create.wire_attempted && !ndi->create.timer_ready &&
        !ndi->create.stats_owned && !ndi->blocked) {
        /* Proven pre-wire failure; native helper returned its stats ID. */
        ndi->active = false;
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        mlme->mgmt.generic.type = WLAN_VDEV_MLME_TYPE_PASSTHRU;
        mlme->proto.generic.nss_2g = 0;
        mlme->proto.generic.nss_5g = 0;
        return ret;
    }
    if (!ndi->create.timer_ready || !ndi->create.wire_accepted ||
        (!ret && !ndi->create.dp_attached))
        ndi->blocked = true;
    if (ndi->blocked)
        ret = -EUCLEAN;
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    return ret;
}

void mishare_runtime_ndi_peer_event(struct wlan_objmgr_psoc *psoc, u8 id,
                                    const u8 *mac, void *owner, bool firmware)
{
    struct mishare_runtime_owner *entry;
    struct mishare_ndi_status *ndi;
    unsigned long flags;

    if (!mac || !owner)
        return;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    for (entry = mishare_runtime_owners; entry; entry = entry->next) {
        if ((void *)entry != owner || entry->psoc != psoc || !entry->vdev ||
            wlan_vdev_get_id(entry->vdev) != id ||
            !ether_addr_equal(entry->mac, mac))
            continue;
        ndi = &entry->state.ndi;
        if (!ndi->active || !ndi->wma_bound || !ndi->peer_created ||
            !ndi->peer_delete_pending || !firmware || ndi->peer_delete_replied) {
            ndi->blocked = true;
            if (!ndi->completion_error)
                ndi->completion_error = -EUCLEAN;
        } else if (!ndi->blocked)
            ndi->peer_delete_replied = true;
        else if (entry->state.rate.late_peer_armed &&
                 entry->state.quiesced == MISHARE_QUIESCE_SSR &&
                 mishare_runtime_rate_peer_inflight(entry)) {
            /* Native hold-request/timer/wake-lock cleanup precedes this origin.
             * Keep quarantine and all parent/NDI ownership in place.
             */
            ndi->peer_delete_replied = true;
            entry->state.rate.late_peer_reply = true;
        }
        break;
    }
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
}

int mishare_runtime_ndi_prepare(struct mishare_runtime_owner *entry)
{
    struct mishare_ndi_status *ndi;
    struct vdev_mlme_obj *mlme;
    unsigned long flags;
    int ret, cleanup;

    if (!entry)
        return -EINVAL;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    ndi = &entry->state.ndi;
    if (entry->state.blocked || ndi->blocked) {
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return -EUCLEAN;
    }
    if (!entry->vdev || entry->state.draining || !ndi->active ||
        !ndi->create.wire_accepted || !ndi->create.dp_attached ||
        ndi->delete_pending || ndi->legacy_ready || ndi->wma_bound ||
        ndi->peer_create_attempted) {
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return -EBUSY;
    }
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    mlme = wlan_vdev_mlme_get_cmpt_obj(entry->vdev);
    ret = mishare_ndi_legacy_prepare(mlme);
    if (ret)
        goto result;
    ndi->legacy_ready = true; /* API calls serialized; no native calls under lock */
    ret = mishare_ndi_wma_bind(entry->vdev);
    if (ret)
        goto local_unwind;
    ndi->wma_bound = true;
    ret = mishare_ndi_self_peer_create(entry->vdev, &ndi->peer_create_attempted);
    if (ret && !ndi->peer_create_attempted && ret != -EUCLEAN)
        goto local_unwind;
    if (ret) {
        spin_lock_irqsave(&mishare_runtime_lock, flags);
        ndi->blocked = true;
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        ret = -EUCLEAN;
    } else {
        ndi->peer_created = true; /* native API success, not firmware confirmation */
    }
    goto result;
local_unwind:
    if (ndi->wma_bound) {
        cleanup = mishare_ndi_wma_unbind(entry->vdev);
        if (cleanup)
            goto failed_unwind;
        ndi->wma_bound = false;
    }
    cleanup = mishare_ndi_legacy_release(mlme);
    if (cleanup)
        goto failed_unwind;
    ndi->legacy_ready = false;
    goto result;
failed_unwind:
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    ndi->blocked = true;
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    ret = -EUCLEAN;
result:
    ndi->context_error = ret;
    return ret;
}

/* MC callback matches the stable owner, exact PSOC and owned VDEV ID. */
void mishare_runtime_ndi_pe_event(struct wlan_objmgr_psoc *psoc, u8 id,
                                   void *owner, bool create,
                                   unsigned long session_cookie, int result)
{
    struct mishare_runtime_owner *entry;
    struct mishare_ndi_status *ndi;
    unsigned long flags;

    spin_lock_irqsave(&mishare_runtime_lock, flags);
    for (entry = mishare_runtime_owners; entry; entry = entry->next) {
        if (entry != owner || entry->psoc != psoc || !entry->vdev ||
            wlan_vdev_get_id(entry->vdev) != id)
            continue;
        ndi = &entry->state.ndi;
        if (!ndi->active || !ndi->peer_created ||
            (create ? (!ndi->pe_requested || ndi->pe_completed ||
                        ndi->pe_delete_requested) :
                       (!ndi->pe_ready || !ndi->pe_delete_requested ||
                        ndi->pe_delete_completed))) {
            ndi->blocked = true;
            if (!ndi->completion_error)
                ndi->completion_error = -EUCLEAN;
            break;
        }
        ndi->pe_error = result;
        if (create) {
            ndi->pe_completed = true;
            if (!result && session_cookie) {
                entry->pe_cookie = session_cookie;
                ndi->pe_ready = true;
            } else if (!result || result == -EUCLEAN) {
                ndi->blocked = true;
                if (!ndi->completion_error)
                    ndi->completion_error = -EUCLEAN;
            }
        } else {
            ndi->pe_delete_completed = true;
            if (result || session_cookie) {
                ndi->blocked = true;
                if (!ndi->completion_error)
                    ndi->completion_error = -EUCLEAN;
            }
            /* pe_ready stays true until post returns and drain consumes ACK. */
        }
        break;
    }
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
}

int mishare_runtime_ndi_session(struct mishare_runtime_owner *entry)
{
    struct mishare_ndi_status *ndi;
    unsigned long flags;
    int ret;

    if (!entry)
        return -EINVAL;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    ndi = &entry->state.ndi;
    if (entry->state.blocked || ndi->blocked) {
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return -EUCLEAN;
    }
    if (!ndi->active || !ndi->legacy_ready || !ndi->wma_bound ||
        !ndi->peer_created || ndi->pe_requested || ndi->peer_delete_pending ||
        ndi->delete_pending || entry->state.draining) {
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return -EBUSY;
    }
    ndi->pe_requested = true;
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    ret = mishare_ndi_pe_post(entry->vdev, entry, true, 0);
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    if (ret) {
        /* Allocation/ref/queue failures precede native queue publication. */
        if (ndi->pe_completed)
            ndi->blocked = true;
        ndi->pe_error = ret;
        ndi->pe_completed = true;
    } else {
        ndi->pe_submitted = true;
    }
    ret = ndi->blocked ? -EUCLEAN : ret ? ret : -EINPROGRESS;
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    return ret;
}

void mishare_runtime_ndi_channel_event(struct wlan_objmgr_psoc *psoc, u8 id,
                                        void *owner, u32 freq, int result)
{
    struct mishare_runtime_owner *entry;
    struct mishare_ndi_status *ndi;
    unsigned long flags;

    spin_lock_irqsave(&mishare_runtime_lock, flags);
    for (entry = mishare_runtime_owners; entry; entry = entry->next) {
        if (entry != owner || entry->psoc != psoc || !entry->vdev ||
            wlan_vdev_get_id(entry->vdev) != id)
            continue;
        ndi = &entry->state.ndi;
        if (!ndi->active || !ndi->pe_ready || !ndi->channel_requested ||
            ndi->channel_completed || ndi->channel_freq != freq ||
            ndi->pe_delete_requested) {
            ndi->blocked = true;
            if (!ndi->completion_error)
                ndi->completion_error = -EUCLEAN;
            break;
        }
        ndi->channel_error = result;
        ndi->channel_completed = true;
        ndi->channel_prepared = !result;
        if (result && result != -EINVAL && result != -EACCES &&
            result != -EBUSY && result != -ECANCELED)
            ndi->blocked = true;
        break;
    }
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
}

int mishare_runtime_ndi_channel(struct mishare_runtime_owner *entry, u32 freq)
{
    struct mishare_ndi_status *ndi;
    unsigned long flags;
    int ret;

    if (!entry || !freq)
        return -EINVAL;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    ndi = &entry->state.ndi;
    if (entry->state.blocked || ndi->blocked) {
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return -EUCLEAN;
    }
    if (!ndi->active || !ndi->legacy_ready || !ndi->wma_bound ||
        !ndi->peer_created || !ndi->pe_submitted || !ndi->pe_completed ||
        !ndi->pe_ready || ndi->channel_requested || ndi->pe_delete_requested ||
        ndi->peer_delete_pending || ndi->delete_pending || entry->state.draining) {
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return -EBUSY;
    }
    ndi->channel_requested = true;
    ndi->channel_freq = freq;
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    ret = mishare_ndi_channel_post(entry->vdev, entry, entry->pe_cookie, freq);
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    if (ret) {
        if (ndi->channel_completed)
            ndi->blocked = true;
        ndi->channel_completed = true;
        ndi->channel_error = ret;
    } else {
        ndi->channel_submitted = true;
    }
    ret = ndi->blocked ? -EUCLEAN : ret ? ret : -EINPROGRESS;
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    return ret;
}

/* Caller holds the runtime registry lock; event identity was matched first. */
static void mishare_runtime_preview_event_locked(struct mishare_runtime_owner *entry,
                     u32 freq, int result, const struct mishare_ndi_start_summary *summary)
{
    struct mishare_start_preview_status *p = &entry->state.start_preview;
    const struct mishare_ndi_status *n = &entry->state.ndi;

    if (!p->requested || p->completed || p->freq != freq || result > 0 ||
        p->vdev_id != wlan_vdev_get_id(entry->vdev) || !n->active ||
        !n->pe_ready || !n->channel_prepared || n->channel_freq != freq ||
        n->start_plan_requested || n->radio_requested || entry->radio || n->pe_delete_requested ||
        (!result && (!summary || summary->freq != freq || summary->center_freq != freq ||
                     !summary->phy_mode || !summary->tx_streams || summary->tx_streams > 2 ||
                     summary->rx_streams != summary->tx_streams))) {
        p->integrity_error = true;
        return;
    }
    p->completed = true;
    p->result = result;
    if (!result)
        p->summary = *summary;
}

int mishare_runtime_start_preview(struct mishare_runtime_owner *owner, u32 freq)
{
    struct mishare_runtime_owner *entry;
    struct mishare_start_preview_status *p;
    const struct mishare_runtime_rate_status *r;
    const struct mishare_runtime_retry_status *retry;
    const struct mishare_ndi_status *n;
    unsigned long flags;
    int ret = -ENOENT;

    if (!owner || !freq)
        return -EINVAL;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    for (entry = mishare_runtime_owners; entry; entry = entry->next)
        if (entry == owner)
            break;
    if (!entry)
        goto unlock;
    p = &entry->state.start_preview;
    n = &entry->state.ndi;
    r = &entry->state.rate;
    retry = &entry->state.retry;
    if (entry->state.quiesced || entry->state.draining || entry->state.freed) {
        ret = -ESHUTDOWN;
        goto unlock;
    }
    if (entry->state.blocked || n->blocked || n->completion_error ||
        entry->state.work_error || r->integrity_error || retry->integrity_error || p->integrity_error) {
        ret = -EUCLEAN;
        goto unlock;
    }
    if (p->requested) {
        if (p->freq != freq) {
            ret = -EBUSY;
            goto unlock;
        }
        ret = mishare_runtime_preview_retire_check(entry);
        if (!ret)
            ret = p->result;
        goto unlock;
    }
    ret = mishare_runtime_preview_retire_check(entry);
    if (ret)
        goto unlock;
    if (!entry->vdev || !entry->referenced || !entry->events ||
        entry->cookie != (unsigned long)entry->vdev || !entry->pe_cookie ||
        !entry->state.allocated || !n->active || !n->legacy_ready || !n->wma_bound ||
        !n->peer_created || !n->pe_submitted || !n->pe_completed || !n->pe_ready ||
        !n->channel_submitted || !n->channel_completed || !n->channel_prepared || n->channel_freq != freq ||
        n->start_plan_requested || n->radio_requested || entry->radio ||
        n->pe_delete_requested || n->peer_delete_pending || n->delete_pending ||
        !entry->state.bssid.requested || !entry->state.bssid.applied || entry->state.bssid.error ||
        !r->requested || !r->posted || !r->accepted || !r->completed ||
        !r->receipt.attempted || !r->receipt.complete || r->receipt.busy ||
        r->receipt.result || r->receipt.first_error || r->receipt.attempted_mask != 7 ||
        r->receipt.submitted_mask != 7 || !retry->requested || !retry->posted ||
        !retry->accepted || !retry->completed || retry->result ||
        !mishare_runtime_retry_receipt_valid(retry, &retry->receipt, 0, wlan_vdev_get_id(entry->vdev))) {
        ret = -EUCLEAN;
        goto unlock;
    }
    if (entry->state.work_pending || entry->state.work_users) {
        ret = -EINPROGRESS;
        goto unlock;
    }
    p->requested = true;
    p->freq = freq;
    p->vdev_id = wlan_vdev_get_id(entry->vdev);
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    ret = mishare_ndi_start_plan_post(entry->vdev, entry, entry->pe_cookie, freq);
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    if (ret) {
        if (p->completed)
            p->integrity_error = true;
        else {
            p->completed = true;
            p->result = ret;
        }
    } else
        p->posted = true;
    ret = p->integrity_error ? -EUCLEAN : ret ? ret : -EINPROGRESS;
unlock:
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    return ret;
}

void mishare_runtime_ndi_start_plan_event(struct wlan_objmgr_psoc *psoc, u8 id,
                                           void *owner, u32 freq, int result,
                                           const struct mishare_ndi_start_summary *summary)
{
    struct mishare_runtime_owner *entry;
    struct mishare_ndi_status *ndi;
    unsigned long flags;

    spin_lock_irqsave(&mishare_runtime_lock, flags);
    for (entry = mishare_runtime_owners; entry; entry = entry->next) {
        if (entry != owner || entry->psoc != psoc || !entry->vdev ||
            wlan_vdev_get_id(entry->vdev) != id)
            continue;
        if (entry->state.start_preview.requested) {
            mishare_runtime_preview_event_locked(entry, freq, result, summary);
            break;
        }
        ndi = &entry->state.ndi;
        if (!ndi->active || !ndi->pe_ready || !ndi->channel_prepared ||
            !ndi->start_plan_requested || ndi->start_plan_completed ||
            ndi->channel_freq != freq || ndi->pe_delete_requested ||
            (!result && (!summary || summary->freq != freq ||
                         summary->center_freq != freq ||
                         !summary->tx_streams || summary->tx_streams > 2 ||
                         summary->rx_streams != summary->tx_streams))) {
            ndi->blocked = true;
            if (!ndi->completion_error)
                ndi->completion_error = -EUCLEAN;
            break;
        }
        ndi->start_plan_error = result;
        ndi->start_plan_completed = true;
        ndi->start_plan_ready = !result;
        if (!result)
            ndi->start_plan = *summary;
        else if (result != -EINVAL && result != -EACCES && result != -EBUSY &&
                 result != -ECANCELED && result != -EOPNOTSUPP)
            ndi->blocked = true;
        break;
    }
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
}

/* No work/native mutation here. The completed owned MC encoder is the
 * provenance; parent/request policy must still be checked by a future caller
 * before real START. This record is not a reusable firmware readiness lease. */
int mishare_runtime_start_plan_commit(struct mishare_runtime_owner *owner, u32 freq)
{
    struct mishare_runtime_owner *entry;
    struct mishare_start_preview_status *p;
    struct mishare_ndi_status *n;
    unsigned long flags;
    int ret = -ENOENT;

    if (!owner || !freq)
        return -EINVAL;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    for (entry = mishare_runtime_owners; entry && entry != owner; entry = entry->next)
        ;
    if (!entry)
        goto unlock;
    p = &entry->state.start_preview;
    n = &entry->state.ndi;
    if (entry->state.quiesced || entry->state.draining || entry->state.freed) {
        ret = -ESHUTDOWN;
        goto unlock;
    }
    if (entry->state.blocked || n->blocked || n->completion_error || entry->state.work_error ||
        entry->state.rate.integrity_error || entry->state.retry.integrity_error) {
        ret = -EUCLEAN;
        goto unlock;
    }
    ret = mishare_runtime_preview_retire_check(entry);
    if (ret)
        goto unlock;
    if (!p->requested || !p->completed) {
        ret = -EINPROGRESS;
        goto unlock;
    }
    if (p->freq != freq) {
        ret = -EBUSY;
        goto unlock;
    }
    if (p->result) {
        ret = p->result;
        goto unlock;
    }
    if (!entry->vdev || !entry->referenced || !entry->events || !entry->pe_cookie ||
        entry->cookie != (unsigned long)entry->vdev || !entry->state.allocated ||
        !n->active || !n->legacy_ready || !n->wma_bound || !n->peer_created || !n->pe_ready ||
        !n->channel_prepared || n->channel_freq != freq ||
        n->radio_requested || entry->radio || n->pe_delete_requested ||
        n->peer_delete_pending || n->delete_pending || n->dp_detaching ||
        entry->state.rate.ordinary_admitted || entry->state.rate.reset_admitted) {
        ret = -EBUSY;
        goto unlock;
    }
    /* Validate original configuration history too; no successful preview can
     * overwrite a later corrupt or partially retired rate/retry receipt. */
    ret = mishare_runtime_rate_retire_check(entry);
    if (ret != -EOPNOTSUPP) {
        if (!ret)
            ret = -EUCLEAN;
        goto unlock;
    }
    if (!entry->state.bssid.requested || !entry->state.bssid.applied || entry->state.bssid.error ||
        !entry->state.rate.requested || !entry->state.rate.posted || !entry->state.rate.accepted ||
        !entry->state.rate.completed || !entry->state.rate.receipt.attempted ||
        !entry->state.rate.receipt.complete || entry->state.rate.receipt.busy ||
        entry->state.rate.receipt.result || entry->state.rate.receipt.first_error ||
        entry->state.rate.receipt.attempted_mask != 7 || entry->state.rate.receipt.submitted_mask != 7 ||
        !entry->state.retry.requested || !entry->state.retry.posted || !entry->state.retry.accepted ||
        !entry->state.retry.completed || entry->state.retry.result ||
        !mishare_runtime_retry_receipt_valid(&entry->state.retry, &entry->state.retry.receipt, 0,
                                             wlan_vdev_get_id(entry->vdev))) {
        ret = -EUCLEAN;
        goto unlock;
    }
    if (!p->committed) {
        if (n->start_plan_requested || n->start_plan_submitted || n->start_plan_completed ||
            n->start_plan_ready || n->start_plan_error || !mishare_preview_summary_empty(&n->start_plan)) {
            ret = -EUCLEAN;
            goto unlock;
        }
        n->start_plan = p->summary;
        n->start_plan_requested = true;
        n->start_plan_submitted = true;
        n->start_plan_completed = true;
        n->start_plan_ready = true;
        p->committed = true;
    }
    ret = 0;
unlock:
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    return ret;
}

int mishare_runtime_ndi_start_plan(struct mishare_runtime_owner *entry)
{
    struct mishare_ndi_status *ndi;
    unsigned long flags;
    int ret;

    if (!entry)
        return -EINVAL;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    ndi = &entry->state.ndi;
    if (entry->state.rate.requested) {
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return -EOPNOTSUPP;
    }

    if (entry->state.blocked || ndi->blocked) {
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return -EUCLEAN;
    }
    if (!entry->vdev || !entry->referenced || !entry->events ||
        !ndi->active || !ndi->legacy_ready || !ndi->wma_bound ||
        !ndi->peer_created || !ndi->pe_ready || !ndi->pe_submitted ||
        !ndi->pe_completed || !ndi->channel_submitted ||
        !ndi->channel_completed || !ndi->channel_prepared ||
        ndi->start_plan_requested || ndi->pe_delete_requested ||
        ndi->peer_delete_pending || ndi->delete_pending || entry->state.draining) {
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return -EBUSY;
    }
    ndi->start_plan_requested = true;
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    ret = mishare_ndi_start_plan_post(entry->vdev, entry, entry->pe_cookie,
                                       ndi->channel_freq);
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    if (ret) {
        if (ndi->start_plan_completed)
            ndi->blocked = true;
        ndi->start_plan_completed = true;
        ndi->start_plan_error = ret;
    } else {
        ndi->start_plan_submitted = true;
    }
    ret = ndi->blocked ? -EUCLEAN : ret ? ret : -EINPROGRESS;
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    return ret;
}

int mishare_runtime_ndi_start(struct mishare_runtime_owner *entry)
{
    struct mishare_ndi_status *ndi;
    unsigned long flags;
    int ret;
    if (!entry)
        return -EINVAL;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    ndi = &entry->state.ndi;
    if (entry->state.rate.requested) {
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return -EOPNOTSUPP;
    }

    if (entry->state.blocked || ndi->blocked) {
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return -EUCLEAN;
    }
    if (!entry->vdev || !entry->referenced || !entry->events ||
        !ndi->active || !ndi->legacy_ready || !ndi->wma_bound ||
        !ndi->peer_created || !ndi->pe_ready || !ndi->channel_prepared ||
        !ndi->start_plan_submitted || !ndi->start_plan_completed ||
        !ndi->start_plan_ready || ndi->radio_requested || entry->radio ||
        ndi->pe_delete_requested || ndi->peer_delete_pending ||
        ndi->delete_pending || entry->state.draining) {
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return -EBUSY;
    }
    ndi->radio_requested = true;
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    ret = mishare_radio_open(entry->vdev, entry->events, entry, entry->pe_cookie,
                              ndi->channel_freq, &ndi->start_plan, &entry->radio);
    if (ret != -EINPROGRESS) {
        spin_lock_irqsave(&mishare_runtime_lock, flags);
        ndi->radio_submit_error = ret;
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    }
    if (ret != -EINPROGRESS && !entry->radio) {
        spin_lock_irqsave(&mishare_runtime_lock, flags);
        entry->state.radio.phase = MISHARE_RADIO_CANCELLED;
        entry->state.radio.error = ret;
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    }
    return ret;
}

static bool
mishare_configured_radio_pristine(const struct mishare_radio_status *r)
{
    const struct mishare_radio_fence_status *f = &r->fence;

    return r->phase == MISHARE_RADIO_NEW && !r->error && !r->closing &&
           !r->start_attempted && !r->stop_attempted && !r->host_up &&
           !r->down_attempted && !r->down_accepted && !r->pending && !r->users &&
           !r->ssr_cancelled_before_start && !r->ssr_start_submit_error &&
           !r->ssr_start_callback_refused && !r->ssr_start_body_aborted &&
           !r->ssr_start_prepared_aborted && !r->ssr_start_sm_entry_aborted &&
           !r->ssr_start_init_rejected && !r->down_fence_callback_seen &&
           !r->down_retire_timer_attempted && !r->down_retire_timer_released &&
           !r->down_retired && !r->down_retire_error &&
           !f->recorded && f->phase == MISHARE_RADIO_NEW && !f->error && !f->closing &&
           !f->start_attempted && !f->stop_attempted && !f->host_up &&
           !f->down_attempted && !f->down_accepted && !f->pending && !f->users &&
           !f->start_sm_entered && !f->start_sm_call_active &&
           !f->start_reply_queued && !f->stop_reply_queued &&
           !f->applying_start_reply && !f->applying_stop_reply;
}

/* Internal configured path. Native scope/canonical policy is the caller's
 * obligation; no public entry, parameter or automatic worker calls this API. */
int mishare_runtime_configured_start(struct mishare_runtime_owner *owner, u32 freq)
{
    struct mishare_runtime_owner *e;
    struct mishare_configured_radio_status *c;
    struct mishare_ndi_status *n;
    unsigned long flags;
    int ret = -ENOENT;

    if (!owner || !freq)
        return -EINVAL;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    for (e = mishare_runtime_owners; e && e != owner; e = e->next)
        ;
    if (!e)
        goto unlock;
    c = &e->state.configured_radio;
    n = &e->state.ndi;
    if (e->state.quiesced || e->state.draining || e->state.freed) {
        ret = -ESHUTDOWN;
        goto unlock;
    }
    if (c->requested) {
        ret = -EALREADY;
        goto unlock;
    }
    if (c->returned || c->stop_requested || c->stopped || c->start_result || c->stop_error ||
        e->state.blocked || n->blocked || e->state.work_error || e->state.recovery_error ||
        e->state.create_error || e->state.reclaim_error || n->completion_error) {
        ret = -EUCLEAN;
        goto unlock;
    }
    if (!e->state.start_preview.committed) {
        ret = -EINPROGRESS;
        goto unlock;
    }
    ret = mishare_runtime_configured_history(e);
    if (ret)
        goto unlock;
    if (freq != e->state.start_preview.freq || !e->vdev || !e->referenced || !e->events ||
        e->cookie != (unsigned long)e->vdev || !e->pe_cookie || !e->state.allocated ||
        e->state.start_preview.vdev_id != wlan_vdev_get_id(e->vdev) ||
        !n->active || !n->legacy_ready || !n->wma_bound || !n->peer_created || !n->pe_ready ||
        !n->pe_submitted || !n->pe_completed || !n->channel_submitted || !n->channel_completed ||
        !n->channel_prepared || !n->create.wire_accepted || !n->create.dp_attached ||
        !n->create.dp_cookie || !n->create.stats_owned || !n->create.timer_ready ||
        n->pe_delete_requested || n->peer_delete_pending || n->delete_pending || n->dp_detaching ||
        e->state.rate.ordinary_admitted || e->state.rate.reset_admitted ||
        n->radio_requested || e->radio || !mishare_configured_radio_pristine(&e->state.radio)) {
        ret = -EUCLEAN;
        goto unlock;
    }
    c->requested = true; /* Before submission: no retry, even on partial failure. */
    n->radio_requested = true;
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    ret = mishare_radio_open(e->vdev, e->events, e, e->pe_cookie,
                            freq, &n->start_plan, &e->radio);
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    c->returned = true;
    c->start_result = ret;
    if (ret != -EINPROGRESS)
        n->radio_submit_error = ret ? ret : -EUCLEAN;
    if (!ret)
        ret = -EUCLEAN; /* An unexpected zero from open is not radio readiness. */
unlock:
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    return ret;
}

/* Component STOP only; resource cleanup stays behind a terminal DOWN receipt.
 * Caller retains every parent and serializes this owner across unlocked calls. */
int mishare_runtime_configured_stop(struct mishare_runtime_owner *owner)
{
    struct mishare_runtime_owner *e;
    struct mishare_configured_radio_status *c;
    struct mishare_radio *radio;
    struct mishare_radio_status observed = {0}, last = {0};
    unsigned long flags;
    int ret = -ENOENT;

    if (!owner)
        return -EINVAL;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    for (e = mishare_runtime_owners; e && e != owner; e = e->next)
        ;
    if (!e)
        goto unlock;
    c = &e->state.configured_radio;
    if (e->state.quiesced || e->state.draining || e->state.freed) {
        ret = -ESHUTDOWN;
        goto unlock;
    }
    if (!c->requested) {
        ret = -EINVAL;
        goto unlock;
    }
    if (!c->returned) {
        ret = -EINPROGRESS;
        goto unlock;
    }
    if (c->stop_error || c->start_result != -EINPROGRESS || e->state.blocked ||
        e->state.ndi.blocked || e->state.work_error || e->state.recovery_error ||
        e->state.reclaim_error || e->state.ndi.completion_error) {
        ret = -EUCLEAN;
        goto unlock;
    }
    ret = mishare_runtime_configured_history(e);
    if (ret)
        goto unlock;
    if (c->stopped) {
        ret = mishare_runtime_configured_down(e) ? 0 : -EUCLEAN;
        goto unlock;
    }
    if (!e->radio || !e->vdev || !e->referenced || !e->events || !e->pe_cookie ||
        e->cookie != (unsigned long)e->vdev || !e->state.ndi.radio_requested ||
        e->state.rate.ordinary_admitted || e->state.rate.reset_admitted ||
        e->state.ndi.pe_delete_requested || e->state.ndi.peer_delete_pending ||
        e->state.ndi.delete_pending || e->state.ndi.dp_detaching) {
        ret = -EUCLEAN;
        goto unlock;
    }
    radio = e->radio;
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    ret = mishare_radio_snapshot(radio, &observed);
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    if (ret || e->radio != radio) {
        ret = -EUCLEAN;
        goto unlock;
    }
    if (e->state.quiesced || observed.fence.recorded || observed.error ||
        observed.phase == MISHARE_RADIO_BLOCKED) {
        ret = -ESHUTDOWN;
        goto unlock;
    }
    if (observed.phase == MISHARE_RADIO_NEW || observed.phase == MISHARE_RADIO_STARTING ||
        observed.phase == MISHARE_RADIO_WAIT_START || observed.pending || observed.users) {
        ret = -EINPROGRESS; /* Do not manufacture pre-UP cancellation support. */
        goto unlock;
    }
    if ((observed.phase != MISHARE_RADIO_UP && observed.phase != MISHARE_RADIO_STOPPING &&
         observed.phase != MISHARE_RADIO_WAIT_STOP && observed.phase != MISHARE_RADIO_DOWN) ||
        !observed.start_attempted || !observed.host_up) {
        ret = -EUCLEAN;
        goto unlock;
    }
    c->stop_requested = true;
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    ret = mishare_radio_drain(&e->radio, &last);
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    e->state.radio = last; /* Native history is retained, never projected/reset. */
    if (!ret) {
        c->stopped = true;
        if (!mishare_runtime_configured_down(e)) {
            c->stopped = false;
            c->stop_error = -EUCLEAN;
            ret = -EUCLEAN;
        }
    } else if (ret != -EINPROGRESS)
        c->stop_error = ret;
unlock:
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    return ret;
}

static void mishare_runtime_ndi_dp_freed(void *context)
{
    struct mishare_runtime_owner *entry;
    struct mishare_ndi_status *ndi;
    unsigned long flags;

    /* Match the opaque callback token before dereference. Native DP calls
     * after storage free; publication is our last access to the owner.
     */
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    for (entry = mishare_runtime_owners; entry; entry = entry->next) {
        if (entry != context)
            continue;
        ndi = &entry->state.ndi;
        if (!ndi->active || !ndi->dp_detaching || !ndi->delete_submitted ||
            !ndi->delete_replied || ndi->dp_freed) {
            ndi->blocked = true;
            if (!ndi->completion_error)
                ndi->completion_error = -EUCLEAN;
        } else if (!ndi->completion_error) {
            ndi->dp_freed = true;
        }
        break;
    }
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    /* Unknown/freed tokens are ignored; no dereference after publication. */
}

static int mishare_runtime_ndi_drain(struct mishare_runtime_owner *entry)
{
    struct mishare_ndi_status *ndi = &entry->state.ndi;
    struct vdev_mlme_obj *mlme;
    unsigned long flags;
    int ret;

    spin_lock_irqsave(&mishare_runtime_lock, flags);
    ret = mishare_runtime_rate_ordinary_check(entry);
    if (ret) {
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return ret;
    }

    ret = entry->state.blocked || ndi->blocked || ndi->completion_error ? -EUCLEAN : 0;
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    if (ret)
        return ret;
    {
        struct mishare_radio_status last = {0};
        bool had_radio = entry->radio != NULL;
        ret = mishare_radio_drain(&entry->radio, &last);
        if (had_radio) {
            spin_lock_irqsave(&mishare_runtime_lock, flags);
            entry->state.radio = last;
            spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        }
        if (ret)
            return ret;
    }
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    if (!ndi->active) {
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return 0;
    }
    if (entry->state.blocked || ndi->blocked) {
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return -EUCLEAN;
    }
    /* Close/drain radio first so queued START sees cancellation. A rate
     * receipt (including zero-attempt flush) still owns its MC reservation:
     * do not advance PE/peer/VDEV cleanup until that reservation is released. */
    if (entry->state.work_pending || entry->state.work_users) {
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return -EINPROGRESS;
    }
    /* A pending MC request owns the VDEV and may publish a PE session. Never
     * advance peer/VDEV/DP cleanup until that request has completed. */
    if (ndi->pe_requested && !ndi->pe_completed) {
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return -EINPROGRESS;
    }
    if (ndi->channel_requested && !ndi->channel_completed) {
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return -EINPROGRESS;
    }
    if (ndi->start_plan_requested && !ndi->start_plan_completed) {
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return -EINPROGRESS;
    }
    if (entry->state.rate.receipt.attempted && !entry->state.rate.ordinary_admitted)
        entry->state.rate.ordinary_admitted = true;
    if (ndi->pe_ready && !ndi->pe_delete_requested) {
        ndi->pe_delete_requested = true;
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        ret = mishare_ndi_pe_post(entry->vdev, entry, false, entry->pe_cookie);
        spin_lock_irqsave(&mishare_runtime_lock, flags);
        ndi->pe_delete_submitted = !ret;
        if (ret)
            ndi->blocked = true;
        ret = ndi->blocked ? -EUCLEAN : -EINPROGRESS;
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return ret;
    }
    if (ndi->pe_ready) {
        if (!ndi->pe_delete_submitted || !ndi->pe_delete_completed) {
            spin_unlock_irqrestore(&mishare_runtime_lock, flags);
            return -EINPROGRESS;
        }
        ndi->pe_ready = false;
        entry->pe_cookie = 0;
    }
    if (ndi->peer_created && !ndi->peer_delete_pending) {
        ndi->peer_delete_pending = true;
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        ret = mishare_ndi_self_peer_delete(entry->vdev, entry);
        spin_lock_irqsave(&mishare_runtime_lock, flags);
        ndi->peer_delete_submitted = !ret;
        if (ret)
            ndi->blocked = true;
        ret = ndi->blocked ? -EUCLEAN : -EINPROGRESS;
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return ret;
    }
    if (ndi->peer_created && (!ndi->peer_delete_submitted ||
                              !ndi->peer_delete_replied)) {
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return -EINPROGRESS;
    }
    if (!ndi->delete_pending) {
        ndi->delete_pending = true;
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        ret = mishare_ndi_native_delete(entry->vdev);
        spin_lock_irqsave(&mishare_runtime_lock, flags);
        ndi->delete_submitted = !ret;
        if (ret)
            ndi->blocked = true;
        ret = ndi->blocked ? -EUCLEAN : -EINPROGRESS;
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return ret;
    }
    if (!ndi->delete_submitted || !ndi->delete_replied) {
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return -EINPROGRESS;
    }
    ndi->create.timer_ready = false; /* real origin completed native deinit */
    if (ndi->create.dp_attempted && !ndi->create.dp_attached) {
        /* Target DP may have published a partially attached vdev on failure.
         * Do not treat failure as no-resource or call an unproven detach path.
         */
        ndi->blocked = true;
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return -EUCLEAN;
    }
    if (ndi->create.dp_attached && !ndi->dp_detaching) {
        ndi->dp_detaching = true;
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        ret = mishare_ndi_native_dp_detach(entry->vdev,
                                           mishare_runtime_ndi_dp_freed, entry);
        spin_lock_irqsave(&mishare_runtime_lock, flags);
        if (ret)
            ndi->blocked = true;
        else {
            ndi->dp_detach_submitted = true;
            ndi->create.stats_owned = false; /* native DP detach reset it */
        }
        ret = ndi->blocked ? -EUCLEAN : -EINPROGRESS;
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return ret;
    }
    if (ndi->create.dp_attached && !ndi->dp_freed) {
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return -EINPROGRESS;
    }
    if (ndi->dp_freed)
        ndi->create.stats_owned = false; /* native DP detach reset this ID */
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    mlme = wlan_vdev_mlme_get_cmpt_obj(entry->vdev);
    if (!mlme || mishare_ndi_release_stats(mlme, &ndi->create)) {
        spin_lock_irqsave(&mishare_runtime_lock, flags);
        ndi->blocked = true;
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return -EUCLEAN;
    }
    if (ndi->wma_bound) {
        if (mishare_ndi_wma_unbind(entry->vdev))
            goto context_blocked;
        ndi->wma_bound = false;
    }
    if (ndi->legacy_ready) {
        if (mishare_ndi_legacy_release(mlme))
            goto context_blocked;
        ndi->legacy_ready = false;
    }
    mlme->mgmt.generic.type = WLAN_VDEV_MLME_TYPE_PASSTHRU;
    mlme->proto.generic.nss_2g = 0;
    mlme->proto.generic.nss_5g = 0;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    ndi->active = false;
    if (entry->state.rate.ordinary_admitted)
        entry->state.rate.ordinary_completed = true;
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    return 0;
context_blocked:
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    ndi->blocked = true;
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    return -EUCLEAN;
}
