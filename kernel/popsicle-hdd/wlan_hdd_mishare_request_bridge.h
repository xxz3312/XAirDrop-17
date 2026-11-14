/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef WLAN_HDD_MISHARE_REQUEST_BRIDGE_H
#define WLAN_HDD_MISHARE_REQUEST_BRIDGE_H
#include "wlan_hdd_mishare_bridge.h"
#include "wlan_hdd_mishare_init.h"

/* Internal typed preparation and explicit configured-START subset. Bind the full canonical request once, but
 * bind host-MLME BSSID and prepare MAC/frequency/NSS/fixed-rate/retry limits.
 * Aggregation enable is rejected; zero flags do not prove firmware disable.
 * Zero is NOT full Wonder initialization or firmware/radio/RX/TX readiness.
 *
 * Same caller serialization, exclusive native transition/RTNL and retained
 * parent/firmware contract as the raw bridge. No automatic lease is acquired.
 * Retire/handoff through the embedded bridge, preserving its authoritative
 * host slot on every partial/error return. Never reset/reuse a live object.
 */
struct mishare_request_bridge {
    struct mishare_bridge bridge;
    struct mishare_init_request request;
    bool bound;
};

static inline int
mishare_request_bridge_step_locked(struct mishare_request_bridge *c,
                                   struct hdd_context *hdd,
                                   const struct mishare_init_request *request,
                                   u8 nss_2g, u8 nss_5g)
{
    struct mishare_init_request canonical;
    struct mishare_bridge *b;
    int ret;

    if (!c || !hdd || !request || !nss_2g || nss_2g > 2 || !nss_5g || nss_5g > 2)
        return -EINVAL;
    b = &c->bridge;
    if (b->closing || b->retired || b->handed_off)
        return -ESHUTDOWN;
    ret = mishare_init_parse(&request->params, &canonical);
    if (ret)
        return ret;
    if (c->bound && (!mishare_init_equal(&c->request, &canonical) ||
        b->hdd != hdd || b->nss_2g != nss_2g || b->nss_5g != nss_5g))
        return -EBUSY;
    if (b->start_error)
        return b->start_error;
    if (!c->bound && (b->host || b->attempted || b->attached || b->hdd || b->prestart_mode))
        return -EBUSY; /* Never adopt an existing raw/foreign bridge. */
    if (c->bound && (!b->prestart_mode || !b->attempted ||
        b->freq != c->request.params.channel.freq ||
        memcmp(b->mac, c->request.params.mac_addr, ETH_ALEN)))
        return mishare_bridge_fail(b, -EUCLEAN);
    ret = mishare_init_aggregation_check(&canonical);
    if (ret)
        return c->bound ? mishare_bridge_fail(b, ret) : ret;
    /* Recheck native current policy on EVERY poll, before allocation, attach,
     * or progression. First refusal leaves a pristine controller untouched. */
    ret = mishare_wonder_request_preflight_locked(hdd, &canonical, nss_2g, nss_5g);
    if (ret)
        return c->bound ? mishare_bridge_fail(b, ret) : ret;
    if (!c->bound) {
        c->request = canonical;
        c->bound = true;
        b->prestart_mode = true;
        b->attempted = true; /* Partial allocation can never be replayed. */
        b->hdd = hdd;
        b->freq = c->request.params.channel.freq;
        b->nss_2g = nss_2g;
        b->nss_5g = nss_5g;
        memcpy(b->mac, c->request.params.mac_addr, ETH_ALEN);
        ret = mishare_wonder_host_create_locked(hdd, b->mac, &b->host);
        if (ret)
            return mishare_bridge_fail(b, ret);
        if (!b->host)
            return mishare_bridge_fail(b, -EUCLEAN);
        return -EINPROGRESS;
    }
    if (!b->host)
        return mishare_bridge_fail(b, -EUCLEAN);
    if (!b->attached) {
        b->attached = true;
        ret = mishare_wonder_host_vdev_create_locked(b->host);
        if (ret)
            return mishare_bridge_fail(b, ret);
        return -EINPROGRESS;
    }
    ret = mishare_wonder_host_bssid_bind_locked(b->host, c->request.params.bssid);
    if (ret == -EINPROGRESS)
        return ret;
    if (ret)
        return mishare_bridge_fail(b, ret);
    ret = mishare_wonder_host_prestart_step_locked(b->host,
                c->request.params.channel.freq, b->nss_2g, b->nss_5g,
                &c->request.params.tx_rate);
    if (ret)
        return ret == -EINPROGRESS ? ret : mishare_bridge_fail(b, ret);
    ret = mishare_wonder_host_retry_step_locked(b->host,
                c->request.params.data_retry_limit, c->request.params.mgmt_retry_limit);
    if (ret && ret != -EINPROGRESS)
        return mishare_bridge_fail(b, ret);
    return ret;
}
/* Read-only fresh-policy/current-owner observation. No preparation, replay,
 * metadata update or START call. Readiness is never cached between scopes. */
static inline int
mishare_request_bridge_validate_locked(const struct mishare_request_bridge *c,
                                     struct hdd_context *hdd,
                                     const struct mishare_init_request *request,
                                     u8 nss_2g, u8 nss_5g)
{
    struct mishare_init_request canonical;
    const struct mishare_bridge *b;
    int ret;

    if (!c || !hdd || !request || !nss_2g || nss_2g > 2 || !nss_5g || nss_5g > 2)
        return -EINVAL;
    b = &c->bridge;
    if (b->closing || b->retired || b->handed_off)
        return -ESHUTDOWN;
    if (!c->bound)
        return -EINPROGRESS;
    ret = mishare_init_parse(&request->params, &canonical);
    if (ret)
        return ret;
    if (!mishare_init_equal(&c->request, &canonical) || b->hdd != hdd ||
        b->nss_2g != nss_2g || b->nss_5g != nss_5g)
        return -EBUSY;
    if (b->start_error)
        return b->start_error;
    if (!b->prestart_mode || !b->attempted || b->retire_broken ||
        b->freq != c->request.params.channel.freq ||
        memcmp(b->mac, c->request.params.mac_addr, ETH_ALEN))
        return -EUCLEAN;
    ret = mishare_wonder_request_preflight_locked(hdd, &canonical, nss_2g, nss_5g);
    if (ret)
        return ret;
    if (!b->host || !b->attached)
        return -EINPROGRESS;
    return 0; /* Bound current request and attached host, no snapshot/commit yet. */
}
static inline int
mishare_request_bridge_ready_locked(const struct mishare_request_bridge *c,
                                     struct hdd_context *hdd,
                                     const struct mishare_init_request *request,
                                     u8 nss_2g, u8 nss_5g)
{
    int ret = mishare_request_bridge_validate_locked(c, hdd, request, nss_2g, nss_5g);

    if (ret)
        return ret;
    return mishare_wonder_host_start_ready_locked(c->bridge.host, &c->request, nss_2g, nss_5g);
}

/* Configuration may finish or a preview may still own MC work. The host
 * rechecks its coherent state before first submission and every result poll. */
static inline int
mishare_request_bridge_plan_step_locked(struct mishare_request_bridge *c,
                                         struct hdd_context *hdd,
                                         const struct mishare_init_request *request,
                                         u8 nss_2g, u8 nss_5g)
{
    int ret = mishare_request_bridge_ready_locked(c, hdd, request, nss_2g, nss_5g);

    if (ret && ret != -EINPROGRESS)
        return ret;
    if (!c->bound || !c->bridge.host || !c->bridge.attached)
        return -EINPROGRESS;
    return mishare_wonder_host_plan_step_locked(c->bridge.host, &c->request, nss_2g, nss_5g);
}
/* Adoption validates the canonical frozen request and CURRENT native policy
 * independently of the old pre-plan observer, including repeated commits. */
static inline int
mishare_request_bridge_plan_commit_step_locked(const struct mishare_request_bridge *c,
                                                struct hdd_context *hdd,
                                                const struct mishare_init_request *request,
                                                u8 nss_2g, u8 nss_5g)
{
    int ret = mishare_request_bridge_validate_locked(c, hdd, request, nss_2g, nss_5g);

    if (ret)
        return ret;
    return mishare_wonder_host_plan_commit_step_locked(c->bridge.host, &c->request, nss_2g, nss_5g);
}
/* Full canonical request and CURRENT native policy are rechecked even after
 * plan adoption. The resulting zero is not a retained START authorization. */
static inline int
mishare_request_bridge_launch_check_locked(const struct mishare_request_bridge *c,
                                            struct hdd_context *hdd,
                                            const struct mishare_init_request *request,
                                            u8 nss_2g, u8 nss_5g)
{
    int ret = mishare_request_bridge_validate_locked(c, hdd, request, nss_2g, nss_5g);

    if (ret)
        return ret;
    return mishare_wonder_host_launch_check_locked(c->bridge.host, &c->request, nss_2g, nss_5g);
}
/* Explicit internal launch, under caller-retained native parents/firmware.
 * Validate full frozen request and CURRENT policy on every attempt, then use
 * the host's fresh committed-state check and runtime one-shot admission.
 * No automatic managed/public caller, cached readiness ticket or UP result. */
static inline int
mishare_request_bridge_configured_start_locked(const struct mishare_request_bridge *c,
                                                struct hdd_context *hdd,
                                                const struct mishare_init_request *request,
                                                u8 nss_2g, u8 nss_5g)
{
    int ret = mishare_request_bridge_validate_locked(c, hdd, request, nss_2g, nss_5g);

    if (ret)
        return ret;
    return mishare_wonder_host_configured_start_locked(c->bridge.host, &c->request, nss_2g, nss_5g);
}

#endif
