// SPDX-License-Identifier: GPL-2.0-only
/* Opt-in PE host registration and multicast routing. SME success is submission,
 * not firmware acceptance or proof of complete RX. Native HDD vdev sync protects
 * the callback's adapter; the owner pointer is compared, never dereferenced. */
#include <linux/errno.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/etherdevice.h>
#include "wlan_hdd_main.h"
#include "sme_api.h"
#include "wlan_hdd_mishare_mgmt_rx.h"

static bool mishare_mgmt_rx;
module_param(mishare_mgmt_rx, bool, 0444);
MODULE_PARM_DESC(mishare_mgmt_rx, "Experimental STA AWDL host mgmt RX routing; default off");
static DEFINE_MUTEX(mishare_mgmt_lock);
/* PE registration matching ignores session ID when replacing a pattern.
 * Use one STA owner globally rather than pretending filters are per-vdev. */
static struct hdd_adapter *mishare_mgmt_owner;
static struct hdd_adapter *mishare_mgmt_reserved;
static bool mishare_mgmt_fault;
static unsigned char mishare_mgmt_prefix[] = {127, 0x00, 0x17, 0xf2, 8};
static atomic64_t mishare_mgmt_routed = ATOMIC64_INIT(0);
static int mishare_mgmt_routed_get(char *buffer, const struct kernel_param *kp)
{
    (void)kp;
    return scnprintf(buffer, PAGE_SIZE, "%lld\n", atomic64_read(&mishare_mgmt_routed));
}
static const struct kernel_param_ops mishare_mgmt_routed_ops = {
    .get = mishare_mgmt_routed_get,
};
module_param_cb(mishare_mgmt_rx_routed, &mishare_mgmt_routed_ops, NULL, 0444);

#include "wlan_mishare_mgmt_diag.h"
static atomic64_t mishare_mgmt_counts[MDIAG_COUNT];
static const char * const mishare_mgmt_names[MDIAG_COUNT] = {
    "register_calls",
    "skip_invalid",
    "skip_mode",
    "skip_ml_adapter",
    "skip_link_adapter",
    "register_submitted",
    "register_failed",
    "register_busy",
    "register_fault",
    "unregister_calls",
    "mac_gone",
    "pe_add_seen",
    "pe_delete_seen",
    "pe_inserted",
    "pe_insert_failed",
    "pe_alloc_failed",
    "pe_check_calls",
    "pe_apple",
    "pe_match_apple",
    "pe_indication_apple",
    "pe_callback_apple",
    "pe_no_callback_apple",
    "hdd_calls",
    "hdd_bad_length",
    "hdd_ineligible",
    "hdd_wrong_link",
    "hdd_no_owner",
    "hdd_bad_flags",
    "hdd_other_prefix",
    "hdd_foreign_da",
    "hdd_apple",
};
void mishare_mgmt_diag_count(enum mishare_mgmt_diag_stage stage)
{
    if (mishare_mgmt_rx && (unsigned int)stage < MDIAG_COUNT)
        atomic64_inc_return(&mishare_mgmt_counts[stage]);
}
void mishare_mgmt_diag_registration(enum mishare_mgmt_diag_stage stage,
                                   unsigned int type, const unsigned char *prefix,
                                   unsigned int length)
{
    if (type == 0xd0 && prefix && length == sizeof(mishare_mgmt_prefix) &&
        !memcmp(prefix, mishare_mgmt_prefix, sizeof(mishare_mgmt_prefix)))
        mishare_mgmt_diag_count(stage);
}
void mishare_mgmt_diag_frame(enum mishare_mgmt_diag_stage stage,
                            const unsigned char *frame, unsigned int length)
{
    if (frame && length >= 29 && length <= 2304 && frame[0] == 0xd0 &&
        !memcmp(frame + 24, mishare_mgmt_prefix, sizeof(mishare_mgmt_prefix)))
        mishare_mgmt_diag_count(stage);
}
static int mishare_mgmt_diag_get(char *buffer, const struct kernel_param *kp)
{
    unsigned int i;
    int used = 0;
    (void)kp;
    for (i = 0; i < MDIAG_COUNT; i++)
        used += scnprintf(buffer + used, PAGE_SIZE - used, "%s=%lld\n",
                          mishare_mgmt_names[i], atomic64_read(&mishare_mgmt_counts[i]));
    /* Each field is an observation; the whole dump is not an atomic snapshot. */
    used += scnprintf(buffer + used, PAGE_SIZE - used,
                      "owner_active=%u\n", (unsigned int)!!smp_load_acquire(&mishare_mgmt_owner));
    return used;
}
static const struct kernel_param_ops mishare_mgmt_diag_ops = {
    .get = mishare_mgmt_diag_get,
};
module_param_cb(mishare_mgmt_rx_diag, &mishare_mgmt_diag_ops, NULL, 0444);

static bool mishare_mgmt_sta(struct hdd_adapter *adapter)
{
    return adapter && adapter->deflink && adapter->dev &&
           adapter->device_mode == QDF_STA_MODE &&
           !hdd_adapter_is_ml_adapter(adapter) &&
           !hdd_adapter_is_link_adapter(adapter) &&
           adapter->deflink->vdev_id != WLAN_UMAC_VDEV_ID_MAX;
}

int mishare_mgmt_rx_register(struct hdd_adapter *adapter)
{
    QDF_STATUS status;
    int ret = 0;
    bool previous;

    if (!mishare_mgmt_rx)
        return 0;
    mishare_mgmt_diag_count(MDIAG_REGISTER_CALLS);
    if (!adapter || !adapter->deflink || !adapter->dev ||
        adapter->deflink->vdev_id == WLAN_UMAC_VDEV_ID_MAX) {
        mishare_mgmt_diag_count(MDIAG_SKIP_INVALID);
        return 0;
    }
    if (adapter->device_mode != QDF_STA_MODE) {
        mishare_mgmt_diag_count(MDIAG_SKIP_MODE);
        return 0;
    }
    if (hdd_adapter_is_ml_adapter(adapter)) {
        mishare_mgmt_diag_count(MDIAG_SKIP_ML_ADAPTER);
        return 0;
    }
    if (hdd_adapter_is_link_adapter(adapter)) {
        mishare_mgmt_diag_count(MDIAG_SKIP_LINK_ADAPTER);
        return 0;
    }
    mutex_lock(&mishare_mgmt_lock);
    if (mishare_mgmt_fault) {
        mishare_mgmt_diag_count(MDIAG_REGISTER_FAULT);
        ret = -ESHUTDOWN;
        goto unlock;
    }
    if (mishare_mgmt_reserved && mishare_mgmt_reserved != adapter) {
        mishare_mgmt_diag_count(MDIAG_REGISTER_BUSY);
        ret = -EBUSY;
        goto unlock;
    }
    /* Re-submit for the same adapter too: native SSR replays registrations.
     * Clear routing before posting; never retain prior success on a failure. */
    previous = mishare_mgmt_reserved == adapter;
    mishare_mgmt_reserved = adapter;
    smp_store_release(&mishare_mgmt_owner, NULL);
    status = sme_register_mgmt_frame(hdd_adapter_get_mac_handle(adapter),
              adapter->deflink->vdev_id, 0x00d0,
              mishare_mgmt_prefix, sizeof(mishare_mgmt_prefix));
    ret = qdf_status_to_os_return(status);
    mishare_mgmt_diag_count(ret ? MDIAG_REGISTER_FAILED : MDIAG_REGISTER_SUBMITTED);
    if (ret && !previous)
        mishare_mgmt_reserved = NULL;
    if (!ret) {
        smp_store_release(&mishare_mgmt_owner, adapter);
        hdd_info("mishare mgmt RX host registration submitted; full firmware RX unverified");
    }
unlock:
    mutex_unlock(&mishare_mgmt_lock);
    return ret;
}

void mishare_mgmt_rx_unregister(struct hdd_adapter *adapter)
{
    QDF_STATUS status;

    mishare_mgmt_diag_count(MDIAG_UNREGISTER_CALLS);
    if (!adapter)
        return;
    mutex_lock(&mishare_mgmt_lock);
    if (mishare_mgmt_reserved != adapter)
        goto unlock;
    smp_store_release(&mishare_mgmt_owner, NULL);
    /* Native deregister_frames may run after MAC teardown. Close this helper
     * without calling SME with a vanished context; do not permit adoption. */
    if (!hdd_adapter_get_mac_handle(adapter)) {
        mishare_mgmt_diag_count(MDIAG_MAC_GONE);
        mishare_mgmt_fault = true;
        mishare_mgmt_reserved = NULL;
        hdd_err("mishare mgmt RX MAC context gone; routing disabled, reload required");
        goto unlock;
    }
    status = sme_deregister_mgmt_frame(hdd_adapter_get_mac_handle(adapter),
              adapter->deflink->vdev_id, 0x00d0,
              mishare_mgmt_prefix, sizeof(mishare_mgmt_prefix));
    if (QDF_IS_STATUS_ERROR(status)) {
        mishare_mgmt_fault = true;
        hdd_err("mishare mgmt RX unregister submission failed; reload required, routing disabled");
    }
    mishare_mgmt_reserved = NULL;
unlock:
    mutex_unlock(&mishare_mgmt_lock);
}

bool mishare_mgmt_rx_route(struct wlan_hdd_link_info *link,
                          const unsigned char *frame, unsigned int length)
{
    struct hdd_adapter *adapter;
    long long count;

    if (!mishare_mgmt_rx)
        return false;
    mishare_mgmt_diag_count(MDIAG_HDD_CALLS);
    if (!link || !frame || length < 40 || length > 2304) {
        mishare_mgmt_diag_count(MDIAG_HDD_BAD_LENGTH);
        return false;
    }
    mishare_mgmt_diag_frame(MDIAG_HDD_APPLE, frame, length);
    adapter = link->adapter;
    if (!mishare_mgmt_sta(adapter)) {
        mishare_mgmt_diag_count(MDIAG_HDD_INELIGIBLE);
        return false;
    }
    if (adapter->deflink != link) {
        mishare_mgmt_diag_count(MDIAG_HDD_WRONG_LINK);
        return false;
    }
    if (smp_load_acquire(&mishare_mgmt_owner) != adapter) {
        mishare_mgmt_diag_count(MDIAG_HDD_NO_OWNER);
        return false;
    }
    if (frame[0] != 0xd0 || (frame[1] & 0xc7) || (frame[22] & 15)) {
        mishare_mgmt_diag_count(MDIAG_HDD_BAD_FLAGS);
        return false;
    }
    if (memcmp(frame + 24, mishare_mgmt_prefix, sizeof(mishare_mgmt_prefix))) {
        mishare_mgmt_diag_count(MDIAG_HDD_OTHER_PREFIX);
        return false;
    }
    if (!is_multicast_ether_addr(frame + 4) &&
        !ether_addr_equal(frame + 4, adapter->dev->dev_addr)) {
        mishare_mgmt_diag_count(MDIAG_HDD_FOREIGN_DA);
        return false;
    }
    count = atomic64_inc_return(&mishare_mgmt_routed);
    if (count <= 3)
        hdd_info("mishare mgmt RX routed candidate bytes=%u; not protocol authentication", length);
    return true;
}
