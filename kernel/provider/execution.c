// SPDX-License-Identifier: GPL-2.0-only
/* External return boundary for the private IPCI SSR callbacks. */
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/errno.h>
#include <linux/string.h>
#include "mishare_wlan_execution.h"

static DEFINE_MUTEX(execution_lock);
static struct mishare_wlan_execution_ops execution_ops;
static unsigned int execution_active;
static bool execution_closing;

int opairshare_wlan_execution_register_v2(const struct mishare_wlan_execution_ops *ops)
{
    int ret = 0;

    if (!ops || !ops->owner || !ops->reinit || !ops->shutdown ||
        !ops->idle_restart || !ops->idle_shutdown)
        return -EINVAL;
    mutex_lock(&execution_lock);
    if (execution_ops.owner) {
        if (execution_ops.owner != ops->owner ||
            execution_ops.reinit != ops->reinit ||
            execution_ops.shutdown != ops->shutdown ||
            execution_ops.idle_restart != ops->idle_restart ||
            execution_ops.idle_shutdown != ops->idle_shutdown)
            ret = -EBUSY;
        else if (execution_closing)
            ret = -ESHUTDOWN;
        else
            ret = -EALREADY;
    } else {
        execution_ops = *ops;
        execution_closing = false;
    }
    mutex_unlock(&execution_lock);
    return ret;
}
EXPORT_SYMBOL(opairshare_wlan_execution_register_v2);

int opairshare_wlan_execution_close(struct module *owner)
{
    int ret = 0;

    if (!owner)
        return -EINVAL;
    mutex_lock(&execution_lock);
    if (execution_ops.owner && execution_ops.owner != owner)
        ret = -EBUSY;
    else if (execution_ops.owner) {
        execution_closing = true;
        if (execution_active)
            ret = -EBUSY;
    }
    mutex_unlock(&execution_lock);
    return ret;
}
EXPORT_SYMBOL(opairshare_wlan_execution_close);

int opairshare_wlan_execution_unregister(struct module *owner)
{
    int ret = 0;

    if (!owner)
        return -EINVAL;
    mutex_lock(&execution_lock);
    if (execution_ops.owner && execution_ops.owner != owner)
        ret = -EBUSY;
    else if (execution_ops.owner) {
        execution_closing = true;
        if (execution_active)
            ret = -EBUSY;
        else {
            memset(&execution_ops, 0, sizeof(execution_ops));
            execution_closing = false;
        }
    }
    mutex_unlock(&execution_lock);
    return ret;
}
EXPORT_SYMBOL(opairshare_wlan_execution_unregister);

static int execution_enter(struct mishare_wlan_execution_ops *ops)
{
    int ret = 0;

    mutex_lock(&execution_lock);
    if (!execution_ops.owner)
        ret = -ENODEV;
    else if (execution_closing)
        ret = -ESHUTDOWN;
    else if (!try_module_get(execution_ops.owner))
        ret = -ESHUTDOWN;
    else {
        *ops = execution_ops;
        execution_active++;
    }
    mutex_unlock(&execution_lock);
    return ret;
}

static void execution_leave(struct module *owner)
{
    mutex_lock(&execution_lock);
    execution_active--;
    mutex_unlock(&execution_lock);
    /* All WLAN frames have returned. Nothing after this put calls WLAN or
     * dereferences its descriptor/HDD. The framework's return PC is external.
     */
    module_put(owner);
}

int opairshare_wlan_execution_reinit(struct device *dev)
{
    struct mishare_wlan_execution_ops ops;
    int ret;

    if (!dev)
        return -EINVAL;
    ret = execution_enter(&ops);
    if (ret)
        return ret;
    ret = ops.reinit(dev);
    execution_leave(ops.owner);
    return ret;
}
EXPORT_SYMBOL(opairshare_wlan_execution_reinit);

void opairshare_wlan_execution_shutdown(struct device *dev)
{
    struct mishare_wlan_execution_ops ops;

    if (!dev || execution_enter(&ops))
        return;
    ops.shutdown(dev);
    execution_leave(ops.owner);
}
EXPORT_SYMBOL(opairshare_wlan_execution_shutdown);


int opairshare_wlan_execution_idle_restart(struct device *dev)
{
    struct mishare_wlan_execution_ops ops;
    int ret;

    if (!dev)
        return -EINVAL;
    ret = execution_enter(&ops);
    if (ret)
        return ret;
    ret = ops.idle_restart(dev);
    execution_leave(ops.owner);
    return ret;
}
EXPORT_SYMBOL(opairshare_wlan_execution_idle_restart);

int opairshare_wlan_execution_idle_shutdown(struct device *dev)
{
    struct mishare_wlan_execution_ops ops;
    int ret;

    if (!dev)
        return -EINVAL;
    ret = execution_enter(&ops);
    if (ret)
        return ret;
    ret = ops.idle_shutdown(dev);
    execution_leave(ops.owner);
    return ret;
}
EXPORT_SYMBOL(opairshare_wlan_execution_idle_shutdown);
