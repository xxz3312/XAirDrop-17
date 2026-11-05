/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef MISHARE_WLAN_EXECUTION_H
#define MISHARE_WLAN_EXECUTION_H
struct module;
struct device;

/* Copied into the external provider; never retained by descriptor address.
 * Native unregister must drain callbacks before WLAN code/data can disappear.
 * These entry points must be registered DIRECTLY with the external framework:
 * calling them through another WLAN trampoline would leave a WLAN return PC.
 */
struct mishare_wlan_execution_ops {
    struct module *owner;
    int (*reinit)(struct device *dev);
    void (*shutdown)(struct device *dev);
};
int opairshare_wlan_execution_register(const struct mishare_wlan_execution_ops *ops);
int opairshare_wlan_execution_close(struct module *owner);
int opairshare_wlan_execution_unregister(struct module *owner);
int opairshare_wlan_execution_reinit(struct device *dev);
void opairshare_wlan_execution_shutdown(struct device *dev);
#endif
