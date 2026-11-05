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
static bool unregister_scope, unregister_pin;
static struct device *unregister_remove_dev;
static int unregister_error;


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
        if (unregister_scope)
            ret = unregister_error ? unregister_error : -EBUSY;
        else if (execution_active)
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
        if (unregister_scope)
            ret = unregister_error ? unregister_error : -EBUSY;
        else if (execution_active)
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


int opairshare_wlan_execution_unregister_begin(struct module *owner, bool borrowed_exit)
{
    int ret = 0;

    if (!owner)
        return -EINVAL;
    mutex_lock(&execution_lock);
    if (!execution_ops.owner)
        ret = -ENOENT;
    else if (execution_ops.owner != owner)
        ret = -EBUSY;
    else if (unregister_scope)
        ret = unregister_error ? unregister_error : -EBUSY;
    else {
        execution_closing = true;
        if (execution_active)
            ret = -EBUSY;
        else if (borrowed_exit != !module_is_live(owner))
            ret = -EINVAL;
        else if (!borrowed_exit && !try_module_get(owner))
            ret = -ESHUTDOWN;
        else {
            unregister_pin = !borrowed_exit;
            unregister_error = 0;
            unregister_remove_dev = NULL;
            unregister_scope = true;
        }
    }
    mutex_unlock(&execution_lock);
    return ret;
}
EXPORT_SYMBOL(opairshare_wlan_execution_unregister_begin);

int opairshare_wlan_execution_remove_begin(struct module *owner, struct device *dev, bool *recorded)
{
    int ret = 0;

    if (!recorded)
        return -EINVAL;
    *recorded = false;
    if (!owner || !dev)
        return -EINVAL;
    mutex_lock(&execution_lock);
    if (execution_ops.owner != owner)
        ret = -ENOENT;
    else if (unregister_scope) {
        if (unregister_error)
            ret = unregister_error;
        else if (unregister_remove_dev) {
            ret = -EBUSY;
            unregister_error = ret;
        }
        else {
            unregister_remove_dev = dev;
            *recorded = true;
        }
    }
    /* Outside the native unregister scope, no receipt or borrowed permission
     * is invented. The existing physical-remove path retains its own contract.
     */
    mutex_unlock(&execution_lock);
    return ret;
}
EXPORT_SYMBOL(opairshare_wlan_execution_remove_begin);

int opairshare_wlan_execution_remove_end(struct module *owner, struct device *dev, int result)
{
    int ret = result;

    mutex_lock(&execution_lock);
    if (!unregister_scope || execution_ops.owner != owner)
        ret = -ENOENT;
    else if (!dev || unregister_remove_dev != dev) {
        ret = -EUCLEAN;
        if (!unregister_error)
            unregister_error = ret;
    } else {
        unregister_remove_dev = NULL;
        if (result && !unregister_error)
            unregister_error = result;
        ret = unregister_error;
    }
    mutex_unlock(&execution_lock);
    return ret;
}
EXPORT_SYMBOL(opairshare_wlan_execution_remove_end);

int opairshare_wlan_execution_unregister_end(struct module *owner, int result)
{
    bool release = false;
    int ret = 0;

    if (!owner)
        return -EINVAL;
    mutex_lock(&execution_lock);
    if (!unregister_scope || execution_ops.owner != owner)
        ret = -ENOENT;
    else {
        if (result && !unregister_error)
            unregister_error = result;
        if (unregister_remove_dev || execution_active)
            ret = -EINPROGRESS;
        else if (unregister_error)
            ret = unregister_error;
        else {
            release = unregister_pin;
            unregister_pin = unregister_scope = false;
            memset(&execution_ops, 0, sizeof(execution_ops));
            execution_closing = false;
        }
    }
    mutex_unlock(&execution_lock);
    /* Live callers retain their own native/file/export execution contract;
     * borrowed exit callers rely on module-exit through the ICNSS drain.
     */
    if (release)
        module_put(owner);
    return ret;
}
EXPORT_SYMBOL(opairshare_wlan_execution_unregister_end);
