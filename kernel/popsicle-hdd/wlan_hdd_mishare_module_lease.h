/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef WLAN_HDD_MISHARE_MODULE_LEASE_H
#define WLAN_HDD_MISHARE_MODULE_LEASE_H
#include <linux/module.h>
#include <linux/errno.h>

/* Serialized by the owning native transition/registry lock. This retains
 * module text only, not HDD, firmware, components or return-to-caller safety.
 * Never copy or reset a live lease. A failed get publishes no reference.
 */
struct mishare_module_lease { bool held; };

static inline int mishare_module_lease_get(struct mishare_module_lease *lease)
{
    if (!lease)
        return -EINVAL;
    if (lease->held)
        return -EBUSY;
    if (!try_module_get(THIS_MODULE))
        return -ESHUTDOWN;
    lease->held = true;
    return 0;
}

static inline void mishare_module_lease_put(struct mishare_module_lease *lease)
{
    if (!lease || !lease->held)
        return;
    lease->held = false;
    module_put(THIS_MODULE);
}
#endif
