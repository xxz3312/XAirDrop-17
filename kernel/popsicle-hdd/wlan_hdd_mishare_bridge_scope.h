/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef WLAN_HDD_MISHARE_BRIDGE_SCOPE_H
#define WLAN_HDD_MISHARE_BRIDGE_SCOPE_H
#include <linux/device.h>
#include <linux/rtnetlink.h>
#include <cds_api.h>
#include "wlan_hdd_main.h"
#include "osif_psoc_sync.h"
#include "wlan_hdd_mishare_bridge.h"

/* Process-context entry only: caller serializes its bridge, pins WLAN text and
 * owns a valid device reference. Caller MUST NOT hold RTNL, a native operation
 * or a transition: wait_for_ops could otherwise wait for that caller itself.
 * Transition acquisition is non-waiting; operation drain can sleep, without
 * RTNL. RTNL is trylocked only after the drain. Never wait with reversed locks.
 *
 * This scope protects ONE call, not asynchronous firmware/component lifetime
 * between polls. It must not be installed in public Wonder callbacks until
 * the caller supplies the remaining native lifetime/SSR coordination.
 */
struct mishare_bridge_scope {
    struct device *dev;
    struct osif_psoc_sync *sync;
    struct hdd_context *hdd;
};

static inline int
mishare_bridge_scope_begin(struct mishare_bridge_scope *scope, struct device *dev)
{
    struct hdd_context *hdd;
    int ret;

    if (!scope || !dev)
        return -EINVAL;
    if (scope->dev || scope->sync || scope->hdd)
        return -EBUSY;
    scope->dev = get_device(dev);
    if (!scope->dev)
        return -ENODEV;
    ret = osif_psoc_sync_trans_start(scope->dev, &scope->sync);
    if (ret)
        goto put_dev;
    osif_psoc_sync_wait_for_ops(scope->sync);
    if (!rtnl_trylock()) {
        ret = -EAGAIN;
        goto stop_trans;
    }
    /* Resolve HDD only inside the acquired native transition, never by
     * dereferencing a bridge's previously borrowed HDD pointer before entry.
     */
    hdd = cds_get_context(QDF_MODULE_ID_HDD);
    if (!hdd || hdd->parent_dev != scope->dev || !hdd->psoc || !hdd->pdev) {
        ret = -ENODEV;
        goto unlock_rtnl;
    }
    scope->hdd = hdd;
    return 0;

unlock_rtnl:
    rtnl_unlock();
stop_trans:
    osif_psoc_sync_trans_stop(scope->sync);
    scope->sync = NULL;
put_dev:
    put_device(scope->dev);
    scope->dev = NULL;
    return ret;
}

/* Only a successfully entered scope may be ended, once, by its caller. */
static inline void mishare_bridge_scope_end(struct mishare_bridge_scope *scope)
{
    scope->hdd = NULL;
    rtnl_unlock();
    osif_psoc_sync_trans_stop(scope->sync);
    scope->sync = NULL;
    put_device(scope->dev);
    scope->dev = NULL;
}

static inline int
mishare_bridge_step(struct mishare_bridge *b, struct device *dev,
                    const u8 *mac, u32 freq, u8 nss_2g, u8 nss_5g)
{
    struct mishare_bridge_scope scope = {0};
    int ret;

    if (!b)
        return -EINVAL;
    ret = mishare_bridge_scope_begin(&scope, dev);
    if (ret)
        return ret; /* No session mutation when native entry is refused. */
    ret = wlan_hdd_validate_context(scope.hdd);
    if (!ret)
        ret = mishare_bridge_step_locked(b, scope.hdd, mac, freq, nss_2g, nss_5g);
    mishare_bridge_scope_end(&scope);
    return ret;
}

static inline int
mishare_bridge_retire(struct mishare_bridge *b, struct device *dev)
{
    struct mishare_bridge_scope scope = {0};
    int ret;

    if (!b)
        return -EINVAL;
    if (b->handed_off)
        return mishare_bridge_poll_retired(b);
    ret = mishare_bridge_scope_begin(&scope, dev);
    if (ret)
        return ret;
    /* Ordinary retirement follows the host's own checks, not a generic health
     * gate which would reject cleanup solely because a start had failed.
     * This does not establish the qualified SSR reset window.
     */
    ret = mishare_bridge_retire_locked(b, scope.hdd);
    mishare_bridge_scope_end(&scope);
    return ret;
}

static inline int
mishare_bridge_handoff_idle(struct mishare_bridge *b, struct device *dev)
{
    struct mishare_bridge_scope scope = {0};
    int ret;

    if (!b)
        return -EINVAL;
    if (b->handed_off)
        return mishare_bridge_poll_retired(b);
    ret = mishare_bridge_scope_begin(&scope, dev);
    if (ret)
        return ret;
    ret = mishare_bridge_handoff_idle_locked(b, scope.hdd);
    mishare_bridge_scope_end(&scope);
    return ret;
}
#endif
