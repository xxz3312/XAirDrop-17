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
    unsigned long cookie;
    u8 mac[ETH_ALEN];
    bool referenced;
    struct mishare_runtime_status state;
};
static DEFINE_SPINLOCK(mishare_runtime_lock);
static struct mishare_runtime_owner *mishare_runtime_owners;
static int mishare_runtime_ndi_drain(struct mishare_runtime_owner *entry);

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
    entry = kzalloc(sizeof(*entry), GFP_KERNEL);
    if (!entry)
        return -ENOMEM;
    entry->psoc = psoc;
    ether_addr_copy(entry->mac, mac);
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    for (other = mishare_runtime_owners; other; other = other->next) {
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
    if (!ndi->active) {
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return 0;
    }
    if (entry->state.blocked || ndi->blocked) {
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        return -EUCLEAN;
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
    mlme->mgmt.generic.type = WLAN_VDEV_MLME_TYPE_PASSTHRU;
    mlme->proto.generic.nss_2g = 0;
    mlme->proto.generic.nss_5g = 0;
    spin_lock_irqsave(&mishare_runtime_lock, flags);
    ndi->active = false;
    spin_unlock_irqrestore(&mishare_runtime_lock, flags);
    return 0;
}
