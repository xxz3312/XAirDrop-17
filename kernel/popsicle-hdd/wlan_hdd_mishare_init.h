/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef WLAN_HDD_MISHARE_INIT_H
#define WLAN_HDD_MISHARE_INIT_H
#include <linux/errno.h>
#include <linux/etherdevice.h>
#include <linux/string.h>
#include "wlan_hdd_mishare_wonder_api.h"

/* Canonical request metadata only. Parsing does not authorize CREATE/START,
 * change country/channel, establish a parent lease or qualify RX/TX.
 * Reserved bytes and an inactive adaptive mask are normalized away.
 */
struct mishare_init_request {
    struct wondertap_init_params params;
};

static inline int
mishare_init_parse(const struct wondertap_init_params *p, struct mishare_init_request *out)
{
    struct mishare_init_request r;

    if (!p || !out || !p->channel.freq || !is_valid_ether_addr(p->mac_addr) ||
        (unsigned int)p->channel.bandwidth > WONDERTAP_RATE_BW_320 ||
        (unsigned int)p->tx_rate.bw > WONDERTAP_RATE_BW_320 ||
        (unsigned int)p->tx_rate.preamble >= WONDERTAP_RATE_PREAMBLE_MAX ||
        (unsigned int)p->tx_rate.gi > WONDERTAP_RATE_GI_3_2_US ||
        !p->tx_rate.nss || p->tx_rate.nss > WONDERTAP_HE_NSS_MAX)
        return -EINVAL;
    if (p->country_code[2] ||
        !((p->country_code[0] >= 'A' && p->country_code[0] <= 'Z' &&
           p->country_code[1] >= 'A' && p->country_code[1] <= 'Z') ||
          (p->country_code[0] == '0' && p->country_code[1] == '0')))
        return -EINVAL;
    if (p->rate_adaptation_enable &&
        ((unsigned int)p->tx_rate_mask.max_preamble >= WONDERTAP_RATE_PREAMBLE_MAX ||
         (unsigned int)p->tx_rate_mask.max_bw > WONDERTAP_RATE_BW_320 ||
         !p->tx_rate_mask.max_nss || p->tx_rate_mask.max_nss > WONDERTAP_HE_NSS_MAX))
        return -EINVAL;
    memset(&r, 0, sizeof(r));
    r.params.channel.freq = p->channel.freq;
    r.params.channel.bandwidth = p->channel.bandwidth;
    r.params.tx_rate.preamble = p->tx_rate.preamble;
    r.params.tx_rate.bw = p->tx_rate.bw;
    r.params.tx_rate.gi = p->tx_rate.gi;
    r.params.tx_rate.nss = p->tx_rate.nss;
    r.params.tx_rate.mcs = p->tx_rate.mcs;
    memcpy(r.params.mac_addr, p->mac_addr, ETH_ALEN);
    memcpy(r.params.bssid, p->bssid, ETH_ALEN);
    memcpy(r.params.country_code, p->country_code, sizeof(r.params.country_code));
    r.params.mgmt_retry_limit = p->mgmt_retry_limit;
    r.params.data_retry_limit = p->data_retry_limit;
    r.params.amsdu_enable = p->amsdu_enable;
    r.params.ampdu_enable = p->ampdu_enable;
    r.params.rate_adaptation_enable = p->rate_adaptation_enable;
    if (p->rate_adaptation_enable) {
        r.params.tx_rate_mask.max_preamble = p->tx_rate_mask.max_preamble;
        r.params.tx_rate_mask.max_bw = p->tx_rate_mask.max_bw;
        r.params.tx_rate_mask.max_nss = p->tx_rate_mask.max_nss;
        r.params.tx_rate_mask.max_mcs = p->tx_rate_mask.max_mcs;
    }
    *out = r;
    return 0;
}

/* Semantic comparison, never a padding-sensitive whole-struct memcmp. */
static inline bool
mishare_init_equal(const struct mishare_init_request *a, const struct mishare_init_request *b)
{
    const struct wondertap_init_params *p = &a->params, *q = &b->params;

    return p->channel.freq == q->channel.freq && p->channel.bandwidth == q->channel.bandwidth &&
        p->tx_rate.preamble == q->tx_rate.preamble && p->tx_rate.bw == q->tx_rate.bw &&
        p->tx_rate.gi == q->tx_rate.gi && p->tx_rate.nss == q->tx_rate.nss && p->tx_rate.mcs == q->tx_rate.mcs &&
        !memcmp(p->mac_addr, q->mac_addr, ETH_ALEN) && !memcmp(p->bssid, q->bssid, ETH_ALEN) &&
        !memcmp(p->country_code, q->country_code, sizeof(p->country_code)) &&
        p->mgmt_retry_limit == q->mgmt_retry_limit && p->data_retry_limit == q->data_retry_limit &&
        p->amsdu_enable == q->amsdu_enable && p->ampdu_enable == q->ampdu_enable &&
        p->rate_adaptation_enable == q->rate_adaptation_enable &&
        p->tx_rate_mask.max_preamble == q->tx_rate_mask.max_preamble &&
        p->tx_rate_mask.max_bw == q->tx_rate_mask.max_bw &&
        p->tx_rate_mask.max_nss == q->tx_rate_mask.max_nss && p->tx_rate_mask.max_mcs == q->tx_rate_mask.max_mcs;
}
#endif
