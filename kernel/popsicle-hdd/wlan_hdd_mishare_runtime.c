// SPDX-License-Identifier: GPL-2.0-only
/* Referenced host vdev ownership. Dormant until called by the DOWN host API. */
#include <linux/errno.h>
#include <linux/etherdevice.h>
#include <linux/slab.h>
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

enum mishare_radio_cancel_origin { MISHARE_CANCEL_FLUSH, MISHARE_CANCEL_REFUSAL, MISHARE_CANCEL_BODY_ABORT, MISHARE_CANCEL_PREPARED_ABORT };

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
            entry->state.recovery_radio_released || entry->state.ndi_reclaim_started) {
            if (!entry->state.ndi.completion_error)
                entry->state.ndi.completion_error = -EUCLEAN;
        } else {
            if (origin == MISHARE_CANCEL_REFUSAL)
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
        if (!entry->state.quiesced)
            entry->state.quiesced = reason;
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
    unsigned long flags;

    if (!owner || !status)
        return -EINVAL;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    *status = owner->state;
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    if (owner->radio)
        return mishare_radio_snapshot(owner->radio, &status->radio);
    return 0;
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

    return entry->state.quiesced == MISHARE_QUIESCE_SSR &&
           entry->state.mc_drained && !entry->state.work_pending && !entry->state.work_users &&
           !entry->state.work_error && !entry->state.reclaim_error && !entry->state.recovery_error &&
           !n->completion_error && !entry->state.recovery_window_closed &&
           !entry->state.ndi_reclaim_started && !entry->state.ndi_reclaim_ready &&
           !entry->state.recovery_radio_start_flushed && !entry->state.recovery_radio_start_refused &&
           !entry->state.recovery_radio_start_aborted && !entry->state.recovery_radio_prepared_aborted &&
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
                         (entry->state.ndi.radio_submit_error != 0);

    return count == 1;
}

static bool mishare_runtime_ndi_recovery_candidate(struct mishare_runtime_owner *entry)
{
    struct mishare_ndi_status *n = &entry->state.ndi;
    bool early, prepared, no_pe, ready_pe, no_channel, ready_channel, no_plan, ready_plan;
    bool no_radio, cancelled_radio;

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
                        !entry->state.radio.start_attempted && !entry->state.radio.host_up &&
                        !entry->state.radio.stop_attempted && !entry->state.radio.down_attempted &&
                        !entry->state.radio.down_accepted));
    return entry->state.quiesced == MISHARE_QUIESCE_SSR &&
           entry->state.mc_drained && !entry->state.work_pending && !entry->state.work_users &&
           !entry->state.work_error && !entry->state.reclaim_error && !entry->state.recovery_error &&
           !n->completion_error &&
           !entry->state.recovery_window_closed && !entry->state.ndi_reclaim_started &&
           !entry->state.host_reclaim && !entry->state.draining &&
           entry->vdev && entry->referenced && entry->events && (no_radio || cancelled_radio) &&
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
        if (entry->psoc == psoc && (mishare_runtime_ndi_recovery_candidate(entry) ||
                                   mishare_runtime_ndi_completed_candidate(entry)))
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
        if (entry->psoc == psoc && (mishare_runtime_ndi_recovery_candidate(entry) ||
                                   mishare_runtime_ndi_completed_candidate(entry)))
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
            txn.state != MISHARE_TXN_QUARANTINED || txn.serial ||
            txn.pending != MISHARE_TXN_NONE || txn.submitted || txn.replied)
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
        if (entry->radio) {
            struct mishare_radio_status radio_observed = {0};

            ret = mishare_radio_ssr_cancel_check(entry->radio, entry->vdev, entry->events,
                                                  entry, entry->pe_cookie, pe_freq);
            if (!ret)
                ret = mishare_radio_snapshot(entry->radio, &radio_observed);
            if (!ret && (radio_observed.ssr_start_prepared_aborted != entry->state.recovery_radio_prepared_aborted ||
                         radio_observed.ssr_start_body_aborted != entry->state.recovery_radio_start_aborted ||
                         radio_observed.ssr_start_callback_refused != entry->state.recovery_radio_start_refused ||
                         radio_observed.error != (entry->state.ndi.radio_submit_error ?
                                                   entry->state.ndi.radio_submit_error : -ESHUTDOWN)))
                ret = -EUCLEAN;
            if (ret)
                return mishare_runtime_recovery_error(entry, ret);
        }
        spin_lock_irqsave(&mishare_runtime_lock, flags);
        entry->state.recovery_timer_attempted = true;
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
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
        if (entry->radio) {
            struct mishare_radio_status last = {0};

            ret = mishare_radio_ssr_cancel_release(&entry->radio, entry->vdev, entry->events,
                                                    entry, entry->pe_cookie, pe_freq, &last);
            if (ret || entry->radio || !last.ssr_cancelled_before_start ||
                last.ssr_start_submit_error != entry->state.ndi.radio_submit_error ||
                last.ssr_start_callback_refused != entry->state.recovery_radio_start_refused ||
                last.ssr_start_body_aborted != entry->state.recovery_radio_start_aborted ||
                last.ssr_start_prepared_aborted != entry->state.recovery_radio_prepared_aborted)
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
            txn.state != MISHARE_TXN_QUARANTINED || txn.serial ||
            txn.pending != MISHARE_TXN_NONE || txn.submitted || txn.replied)
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
            txn.state != MISHARE_TXN_QUARANTINED || txn.serial ||
            txn.pending != MISHARE_TXN_NONE || txn.submitted || txn.replied)
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
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    return mishare_runtime_host_destroy(owner, true);
}

/* Registry lock held. Pure metadata only: no native pointer is dereferenced. */
static bool mishare_runtime_final_shape_valid(struct mishare_runtime_owner *entry)
{
    struct mishare_ndi_status *n = &entry->state.ndi;

    return ((!entry->state.recovery_radio_start_flushed && !entry->state.recovery_radio_start_refused &&
             !entry->state.recovery_radio_start_aborted && !entry->state.recovery_radio_prepared_aborted &&
           !entry->state.recovery_radio_released) ||
            (mishare_runtime_radio_origin_valid(entry) &&
             entry->state.recovery_radio_released &&
             n->radio_requested && entry->state.radio.ssr_cancelled_before_start &&
             entry->state.radio.phase == MISHARE_RADIO_BLOCKED &&
             entry->state.radio.ssr_start_submit_error == n->radio_submit_error &&
             entry->state.radio.ssr_start_callback_refused == entry->state.recovery_radio_start_refused &&
             entry->state.radio.ssr_start_body_aborted == entry->state.recovery_radio_start_aborted &&
             entry->state.radio.ssr_start_prepared_aborted == entry->state.recovery_radio_prepared_aborted &&
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
    if (!ret)
        kfree(entry);
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
    entry = kzalloc(sizeof(*entry), GFP_KERNEL);
    if (!entry)
        return -ENOMEM;
    entry->psoc = psoc;
    ether_addr_copy(entry->mac, mac);
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    for (other = mishare_runtime_owners; other; other = other->next) {
        if (other->psoc == psoc && other->state.quiesced) {
            spin_unlock_irqrestore(&mishare_runtime_lock, flags);
            kfree(entry);
            return -EUCLEAN;
        }
        if (other->psoc == psoc && ether_addr_equal(other->mac, mac)) {
            spin_unlock_irqrestore(&mishare_runtime_lock, flags);
            kfree(entry);
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
        break;
    }
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
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
            !ndi->peer_delete_pending || !firmware || ndi->peer_delete_replied)
            ndi->blocked = true;
        else if (!ndi->blocked)
            ndi->peer_delete_replied = true;
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

int mishare_runtime_ndi_start_plan(struct mishare_runtime_owner *entry)
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
    ret = entry->state.blocked || ndi->blocked || ndi->completion_error;
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    if (ret)
        return -EUCLEAN;
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
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    return 0;
context_blocked:
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    ndi->blocked = true;
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    return -EUCLEAN;
}
