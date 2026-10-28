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

bool mishare_runtime_work_allowed(struct wlan_objmgr_vdev *vdev, void *owner)
{
    struct mishare_runtime_owner *entry;
    struct wlan_objmgr_psoc *psoc;
    unsigned long flags;
    bool allowed = false;
    if (!vdev || !owner)
        return false;
    psoc = wlan_vdev_get_psoc(vdev);
    if (!mishare_runtime_platform_available(psoc)) {
        mishare_runtime_quiesce_psoc(psoc, MISHARE_QUIESCE_UNAVAILABLE);
        return false;
    }
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

int mishare_runtime_destroy(struct mishare_runtime_owner **owner)
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
    ret = mishare_runtime_ndi_drain(entry);
    if (ret)
        return ret;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    if (entry->state.blocked) {
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return -EUCLEAN;
    }
    if (!entry->state.draining && entry->vdev) {
        entry->state.draining = true;
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        vdev = entry->vdev;
        status = wlan_objmgr_vdev_obj_delete(vdev);
        if (status != QDF_STATUS_SUCCESS) {
            spin_lock_irqsave(&mishare_runtime_lock, flags);
            entry->state.blocked = true;
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
            spin_unlock_irqrestore(&mishare_runtime_lock, flags);
            return -EUCLEAN;
        }
        referenced = entry->referenced;
        entry->referenced = false;
        entry->vdev = NULL;
        if (referenced)
            wlan_objmgr_vdev_release_ref(vdev, WLAN_HDD_ID_OBJ_MGR);
        spin_lock_irqsave(&mishare_runtime_lock, flags);
    }
    if (entry->state.blocked) {
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
        if (!firmware || !ndi->delete_pending || ndi->delete_replied)
            ndi->blocked = true;
        else if (!ndi->blocked)
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
            }
        } else {
            ndi->pe_delete_completed = true;
            if (result || session_cookie)
                ndi->blocked = true;
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
                              ndi->channel_freq, &entry->radio);
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
    struct mishare_runtime_owner *entry = context;
    unsigned long flags;

    /* Native DP calls this after its actual vdev storage has been freed.
     * The owner cannot disappear while active/detaching is set.
     */
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    entry->state.ndi.dp_freed = true;
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
}

static int mishare_runtime_ndi_drain(struct mishare_runtime_owner *entry)
{
    struct mishare_ndi_status *ndi = &entry->state.ndi;
    struct vdev_mlme_obj *mlme;
    unsigned long flags;
    int ret;

    spin_lock_irqsave(&mishare_runtime_lock, flags);
    ret = entry->state.blocked || ndi->blocked;
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
        else
            ndi->create.stats_owned = false; /* native DP detach reset it */
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
