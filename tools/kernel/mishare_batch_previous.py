"""Immutable stage-0027 batch function for the Actions negative control."""
PREVIOUS_BATCH_FUNCTION = r'''int mishare_runtime_reclaim_batch(struct wlan_objmgr_psoc *psoc,
                                  struct mishare_runtime_reclaim_item *items,
                                  unsigned int count)
{
    struct mishare_runtime_owner *entry;
    unsigned long flags;
    unsigned int i, j;
    bool found, ndi;
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
        if (entry->state.quiesced != MISHARE_QUIESCE_SSR) {
            ret = -ESHUTDOWN;
            goto unlock;
        }
        if (entry->state.work_error || entry->state.reclaim_error ||
            entry->state.recovery_error) {
            ret = -EUCLEAN;
            goto unlock;
        }
        if (!entry->state.mc_drained || entry->state.work_pending ||
            entry->state.work_users) {
            ret = -EINPROGRESS;
            goto unlock;
        }
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
        ndi = entry->state.ndi.active || entry->state.ndi.create.wire_attempted ||
              entry->state.ndi_reclaim_started || entry->state.ndi_reclaim_ready;
        spin_unlock_irqrestore(&mishare_runtime_lock, flags);
        ret = ndi ? mishare_runtime_reclaim_ndi(&items[i].owner) :
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
}'''
