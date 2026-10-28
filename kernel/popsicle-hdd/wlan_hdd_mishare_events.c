// SPDX-License-Identifier: GPL-2.0-only
/* Native event provenance and transaction registry. No bound runtime owner yet. */
#include <linux/errno.h>
#include <linux/bug.h>
#include <linux/slab.h>
#include <linux/spinlock.h>
#include <wlan_objmgr_vdev_obj.h>
#include "wlan_hdd_mishare_events.h"

struct mishare_event_owner {
    struct mishare_event_owner *next;
    struct wlan_objmgr_psoc *psoc;
    struct wlan_objmgr_vdev *vdev;
    struct mishare_vdev_txn txn;
};

static DEFINE_SPINLOCK(mishare_events_lock);
static struct mishare_event_owner *mishare_event_owners;

void mishare_events_quiesce_psoc(struct wlan_objmgr_psoc *psoc)
{
    struct mishare_event_owner *entry;
    unsigned long flags;
    if (!psoc)
        return;
    spin_lock_irqsave(&mishare_events_lock, flags);
    for (entry = mishare_event_owners; entry; entry = entry->next)
        if (entry->psoc == psoc)
            entry->txn.state = MISHARE_TXN_QUARANTINED;
    spin_unlock_irqrestore(&mishare_events_lock, flags);
}

int mishare_events_bind(struct wlan_objmgr_vdev *vdev,
                        struct mishare_event_owner **owner)
{
    struct mishare_event_owner *entry, *other;
    struct wlan_objmgr_psoc *psoc;
    unsigned long flags;
    int ret = 0;

    if (!owner || !vdev)
        return -EINVAL;
    if (*owner)
        return -EBUSY;
    if (wlan_objmgr_vdev_try_get_ref(vdev, WLAN_HDD_ID_OBJ_MGR) !=
        QDF_STATUS_SUCCESS)
        return -ENODEV;
    if (wlan_vdev_mlme_get_opmode(vdev) != QDF_PASSTHRU_MODE) {
        ret = -EOPNOTSUPP;
        goto release_ref;
    }
    psoc = wlan_vdev_get_psoc(vdev);
    if (!psoc) {
        ret = -ENODEV;
        goto release_ref;
    }
    entry = kzalloc(sizeof(*entry), GFP_KERNEL);
    if (!entry) {
        ret = -ENOMEM;
        goto release_ref;
    }
    entry->psoc = psoc;
    entry->vdev = vdev;
    mishare_vdev_txn_init(&entry->txn, wlan_vdev_get_id(vdev));
    spin_lock_irqsave(&mishare_events_lock, flags);
    for (other = mishare_event_owners; other; other = other->next) {
        if (other->psoc == psoc && other->txn.vdev_id == entry->txn.vdev_id) {
            ret = -EEXIST;
            break;
        }
    }
    if (!ret) {
        entry->next = mishare_event_owners;
        mishare_event_owners = entry;
    }
    spin_unlock_irqrestore(&mishare_events_lock, flags);
    if (ret) {
        kfree(entry);
        goto release_ref;
    }
    *owner = entry;
    return 0;

release_ref:
    wlan_objmgr_vdev_release_ref(vdev, WLAN_HDD_ID_OBJ_MGR);
    return ret;
}

void mishare_events_unbind(struct mishare_event_owner **owner)
{
    struct mishare_event_owner *entry, **link;
    struct wlan_objmgr_vdev *vdev;
    unsigned long flags;

    if (!owner || !*owner)
        return;
    entry = *owner;
    spin_lock_irqsave(&mishare_events_lock, flags);
    for (link = &mishare_event_owners; *link && *link != entry;
         link = &(*link)->next)
        ;
    if (WARN_ON(!*link)) {
        spin_unlock_irqrestore(&mishare_events_lock, flags);
        return;
    }
    *link = entry->next;
    *owner = NULL;
    spin_unlock_irqrestore(&mishare_events_lock, flags);
    /* All notifier accesses completed under the same lock; none retain entry.
     * Release the object reference outside that lock (may trigger destruction).
     */
    vdev = entry->vdev;
    kfree(entry);
    wlan_objmgr_vdev_release_ref(vdev, WLAN_HDD_ID_OBJ_MGR);
}

int mishare_events_begin(struct mishare_event_owner *owner,
                         enum mishare_txn_command command, u64 *ticket)
{
    unsigned long flags;
    int ret;

    if (!owner) {
        if (ticket)
            *ticket = 0;
        return -EINVAL;
    }
    spin_lock_irqsave(&mishare_events_lock, flags);
    ret = mishare_vdev_txn_begin(&owner->txn, command, ticket);
    spin_unlock_irqrestore(&mishare_events_lock, flags);
    return ret;
}

int mishare_events_begin_vdev(struct mishare_event_owner *owner,
                              struct wlan_objmgr_vdev *vdev,
                              enum mishare_txn_command command, u64 *ticket)
{
    unsigned long flags;
    int ret;

    if (!ticket)
        return -EINVAL;
    *ticket = 0;
    if (!owner || !vdev)
        return -EINVAL;
    spin_lock_irqsave(&mishare_events_lock, flags);
    if (owner->vdev != vdev)
        ret = -EXDEV;
    else
        ret = mishare_vdev_txn_begin(&owner->txn, command, ticket);
    spin_unlock_irqrestore(&mishare_events_lock, flags);
    return ret;
}

int mishare_events_submitted(struct mishare_event_owner *owner, u64 ticket,
                             enum mishare_txn_delivery delivery)
{
    unsigned long flags;
    int ret;

    if (!owner)
        return -EINVAL;
    spin_lock_irqsave(&mishare_events_lock, flags);
    ret = mishare_vdev_txn_submitted(&owner->txn, ticket, delivery);
    spin_unlock_irqrestore(&mishare_events_lock, flags);
    return ret;
}

int mishare_events_snapshot(struct mishare_event_owner *owner,
                            struct mishare_vdev_txn *snapshot)
{
    unsigned long flags;

    if (!owner || !snapshot)
        return -EINVAL;
    spin_lock_irqsave(&mishare_events_lock, flags);
    *snapshot = owner->txn;
    spin_unlock_irqrestore(&mishare_events_lock, flags);
    return 0;
}

int mishare_events_notify(struct wlan_objmgr_psoc *psoc, u8 vdev_id,
                          enum mishare_txn_command command,
                          enum mishare_event_origin origin, bool success)
{
    struct mishare_event_owner *entry;
    unsigned long flags;
    int ret = -ENOENT;

    if (!psoc || (command != MISHARE_TXN_START && command != MISHARE_TXN_STOP) ||
        (origin != MISHARE_EVENT_FIRMWARE && origin != MISHARE_EVENT_TIMEOUT))
        return -EINVAL;
    spin_lock_irqsave(&mishare_events_lock, flags);
    for (entry = mishare_event_owners; entry; entry = entry->next) {
        if (entry->psoc != psoc || entry->txn.vdev_id != vdev_id)
            continue;
        if (origin == MISHARE_EVENT_FIRMWARE) {
            ret = mishare_vdev_txn_response(&entry->txn, vdev_id, command, success);
        } else if (entry->txn.state == MISHARE_TXN_QUARANTINED) {
            ret = -EUCLEAN;
        } else if (entry->txn.pending != command) {
            ret = -ENOENT;
        } else {
            ret = mishare_vdev_txn_timeout(&entry->txn, entry->txn.serial);
        }
        break;
    }
    spin_unlock_irqrestore(&mishare_events_lock, flags);
    return ret;
}
