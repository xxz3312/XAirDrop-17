/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef MISHARE_WLAN_EXECUTION_H
#define MISHARE_WLAN_EXECUTION_H
#include <linux/types.h>
struct module;
struct device;
struct pci_dev;
struct pci_device_id;

/* V2 registration has a distinct export: old three-entry descriptors must
 * never be read as this larger callback table. Rebuild provider and WLAN as
 * a matched pair; no v1 registration alias is exported.
 * Copied into the external provider; never retained by descriptor address.
 * Native unregister must drain callbacks before WLAN code/data can disappear.
 * These entry points must be registered DIRECTLY with the external framework:
 * calling them through another WLAN trampoline would leave a WLAN return PC.
 */
struct mishare_wlan_execution_ops {
    struct module *owner;
    int (*reinit)(struct device *dev);
    void (*shutdown)(struct device *dev);
    int (*idle_restart)(struct device *dev);
    int (*idle_shutdown)(struct device *dev);
};
int opairshare_wlan_execution_register_v2(const struct mishare_wlan_execution_ops *ops);
/* V3 has PCIe-native signatures, including the original device ID. V2's
 * layout and export remain unchanged. Exactly one transport can register.
 * These four entries are prepared for CNSS2 integration; exporting them alone
 * does not connect the native CNSS2 registration/unregister lifecycle.
 */
struct mishare_wlan_pcie_execution_ops {
    struct module *owner;
    int (*reinit)(struct pci_dev *pdev, const struct pci_device_id *id);
    void (*shutdown)(struct pci_dev *pdev);
    int (*idle_restart)(struct pci_dev *pdev, const struct pci_device_id *id);
    int (*idle_shutdown)(struct pci_dev *pdev);
};
int opairshare_wlan_execution_register_pcie_v3(const struct mishare_wlan_pcie_execution_ops *ops);
int opairshare_wlan_execution_pcie_reinit(struct pci_dev *pdev, const struct pci_device_id *id);
void opairshare_wlan_execution_pcie_shutdown(struct pci_dev *pdev);
int opairshare_wlan_execution_pcie_idle_restart(struct pci_dev *pdev, const struct pci_device_id *id);
int opairshare_wlan_execution_pcie_idle_shutdown(struct pci_dev *pdev);
int opairshare_wlan_execution_close(struct module *owner);
int opairshare_wlan_execution_unregister(struct module *owner);
int opairshare_wlan_execution_reinit(struct device *dev);
void opairshare_wlan_execution_shutdown(struct device *dev);
int opairshare_wlan_execution_idle_restart(struct device *dev);
int opairshare_wlan_execution_idle_shutdown(struct device *dev);
/* Only a native unregister caller retaining WLAN execution through the whole
 * ICNSS drain may request borrowed_exit. GOING cannot acquire a new reference.
 * A live failure keeps its scope pin; no force-reset API is provided.
 */
int opairshare_wlan_execution_unregister_begin(struct module *owner, bool borrowed_exit);
int opairshare_wlan_execution_unregister_end(struct module *owner, int result);
int opairshare_wlan_execution_remove_begin(struct module *owner, struct device *dev, bool *recorded);
int opairshare_wlan_execution_remove_end(struct module *owner, struct device *dev, int result);
/* Read-only observation for a matched checked platform callback. */
int opairshare_wlan_execution_remove_status(struct device *dev);
#endif
