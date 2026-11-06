/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef WLAN_HDD_MISHARE_BRIDGE_H
#define WLAN_HDD_MISHARE_BRIDGE_H
#include <linux/errno.h>
#include <linux/etherdevice.h>
#include <linux/string.h>
#include "wlan_hdd_mishare_host.h"

/* Caller-owned, zero-initialized once; never reset/reuse a live or retired
 * bridge. Caller serializes every call, owns RTNL + exclusive PSOC transition
 * during native calls, and retains the SAME HDD/components/firmware lifetime
 * between polls until retirement succeeds. This object DOES NOT acquire that
 * lease. Host object/module references do not replace it.
 *
 * This joins host allocation, runtime attachment and asynchronous radio start.
 * A zero step result means radio UP only, NOT Wonder init/RX/TX readiness.
 * No public Wonder callback, worker, module parameter or automatic teardown
 * invokes this helper; parent coordination and data-plane setup remain pending.
 */
struct mishare_bridge {
    struct mishare_wonder_host *host;
    struct hdd_context *hdd;
    u8 mac[ETH_ALEN];
    u32 freq;
    u8 nss_2g, nss_5g;
    bool attempted, attached, closing, retired, retire_broken;
    int start_error;
};

static inline int mishare_bridge_fail(struct mishare_bridge *b, int error)
{
    if (!b->start_error)
        b->start_error = error;
    return b->start_error;
}

static inline int
mishare_bridge_step_locked(struct mishare_bridge *b, struct hdd_context *hdd,
                           const u8 *mac, u32 freq, u8 nss_2g, u8 nss_5g)
{
    int ret;

    if (!b || !hdd || !mac || !is_valid_ether_addr(mac) || !freq ||
        !nss_2g || nss_2g > 2 || !nss_5g || nss_5g > 2)
        return -EINVAL;
    if (b->closing || b->retired)
        return -ESHUTDOWN;
    if (b->attempted && (b->hdd != hdd || b->freq != freq ||
        b->nss_2g != nss_2g || b->nss_5g != nss_5g ||
        memcmp(b->mac, mac, ETH_ALEN)))
        return -EBUSY;
    if (b->start_error)
        return b->start_error;
    if (!b->attempted) {
        if (b->host) /* Never adopt a foreign or partly initialized owner. */
            return mishare_bridge_fail(b, -EUCLEAN);
        b->attempted = true; /* Failed allocation is not permission to replay. */
        b->hdd = hdd;
        b->freq = freq;
        b->nss_2g = nss_2g;
        b->nss_5g = nss_5g;
        memcpy(b->mac, mac, ETH_ALEN);
        ret = mishare_wonder_host_create_locked(hdd, b->mac, &b->host);
        if (ret)
            return mishare_bridge_fail(b, ret);
        if (!b->host)
            return mishare_bridge_fail(b, -EUCLEAN);
        return -EINPROGRESS; /* DOWN host allocation is not radio readiness. */
    }
    if (!b->host)
        return mishare_bridge_fail(b, -EUCLEAN);
    if (!b->attached) {
        /* Mark before submission; even a partial failure is not replayable. */
        b->attached = true;
        ret = mishare_wonder_host_vdev_create_locked(b->host);
        if (ret)
            return mishare_bridge_fail(b, ret);
        return -EINPROGRESS;
    }
    ret = mishare_wonder_host_session_step_locked(b->host, b->freq,
                                                 b->nss_2g, b->nss_5g);
    if (ret && ret != -EINPROGRESS)
        return mishare_bridge_fail(b, ret);
    return ret;
}

static inline int
mishare_bridge_retire_locked(struct mishare_bridge *b, struct hdd_context *hdd)
{
    int ret;

    if (!b || !hdd)
        return -EINVAL;
    if (b->hdd && b->hdd != hdd)
        return -EBUSY;
    b->closing = true; /* Permanent admission close, even while drain waits. */
    if (!b->attempted && b->host)
        b->retire_broken = true; /* Never free an unadopted foreign owner. */
    if (b->retire_broken)
        return -EUCLEAN;
    if (b->retired)
        return 0;
    if (b->host) {
        /* Pass the authoritative slot, including every partial/error result.
         * Never NULL it before the host reports final destruction.
         */
        ret = mishare_wonder_host_destroy_locked(&b->host);
        if ((!ret && b->host) || (ret && !b->host)) {
            b->retire_broken = true;
            return -EUCLEAN;
        }
        if (ret)
            return ret;
    }
    b->retired = true;
    return 0;
}
#endif
