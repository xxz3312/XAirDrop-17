// SPDX-License-Identifier: GPL-2.0-only
/* DT-free Wonder component bridge. Does not own the PCIe/WLAN device. */
#include <linux/component.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/platform_device.h>

#include "wondertap.h"
#include "../wonder/wondertap_managed.h"

#define PROVIDER_NAME "qcom,cnss-vendor-wlan-wonder"

static DEFINE_MUTEX(provider_lock);
static struct platform_device *provider;
static const struct wondertap_priv *active_priv;
static bool component_registered;
/* Never hold this mutex across component_add/del. Core bind/unbind may call
 * control synchronously while provider_lock is already held. RELEASE shares
 * this lock with preflight, keeping cookie memory live through quiesce.
 */
static DEFINE_MUTEX(provider_claim_lock);
static const struct wondertap_managed_ops *active_managed;
static bool provider_closing;
static void *claim_cookie;
static int (*claim_quiesce)(void *);

int opairshare_wonder_managed_control(enum wondertap_provider_command command,
		const void *priv, void *cookie, int (*quiesce)(void *),
		const struct wondertap_managed_ops **managed)
{
	int ret = 0;
	mutex_lock(&provider_claim_lock);
	if (!priv || active_priv != priv) {
		ret = -ENOENT;
		goto out;
	}
	if (command == WONDERTAP_PROVIDER_RELEASE) {
		if (claim_cookie && claim_cookie != cookie)
			ret = -ENOENT;
		else {
			claim_cookie = NULL;
			claim_quiesce = NULL;
		}
		goto out;
	}
	if (provider_closing) {
		ret = -ESHUTDOWN;
		goto out;
	}
	if (!active_managed) {
		ret = -EOPNOTSUPP;
		goto out;
	}
	switch (command) {
	case WONDERTAP_PROVIDER_QUERY:
		if (!managed)
			ret = -EINVAL;
		else
			*managed = active_managed;
		break;
	case WONDERTAP_PROVIDER_CLAIM:
		if (!cookie || !quiesce)
			ret = -EINVAL;
		else if (claim_cookie &&
				 (claim_cookie != cookie || claim_quiesce != quiesce))
			ret = -EBUSY;
		else {
			claim_cookie = cookie;
			claim_quiesce = quiesce;
		}
		break;
	default:
		ret = -EINVAL;
		break;
	}
out:
	mutex_unlock(&provider_claim_lock);
	return ret;
}
EXPORT_SYMBOL(opairshare_wonder_managed_control);

static int provider_bind(struct device *dev, struct device *master, void *data)
{
	dev_info(dev, "vendor wonder bound to master device %s\n", dev_name(master));
	return 0;
}

static void provider_unbind(struct device *dev, struct device *master, void *data)
{
	dev_info(dev, "vendor wonder unbound from master device %s\n", dev_name(master));
}

static const struct component_ops provider_ops = {
	.bind = provider_bind,
	.unbind = provider_unbind,
};

/* Private bridge API: must not shadow any stock CNSS export.
 * Caller owns priv and its callbacks until the matching NULL call returns.
 * Never call this function from a component bind/unbind callback.
 */
int opairshare_set_wonder_managed_priv_data(const void *priv_data,
				 const struct wondertap_managed_ops *managed)
{
	const struct wondertap_priv *priv = priv_data;
	int ret = 0;

	mutex_lock(&provider_lock);
	if (!provider) {
		ret = -ENODEV;
		goto out;
	}
	if (priv) {
		if (!priv->wonder_ops || priv->ver < 0 || priv->ver >= WONDER_VERSION_MAX ||
			(managed && (managed->ops != priv->wonder_ops || !managed->owner ||
						 !managed->poll_start || !managed->retire))) {
			ret = -EINVAL;
			goto out;
		}
		mutex_lock(&provider_claim_lock);
		if (active_priv) {
			ret = provider_closing ? -ESHUTDOWN :
				  active_priv == priv && active_managed == managed ? 0 : -EBUSY;
			mutex_unlock(&provider_claim_lock);
			goto out;
		}
		active_priv = priv;
		active_managed = managed;
		provider_closing = false;
		mutex_unlock(&provider_claim_lock);
		platform_set_drvdata(provider, (void *)priv);
		ret = component_add(&provider->dev, &provider_ops);
		if (ret) {
			/* A failed master bind must release any accepted claim itself. */
			mutex_lock(&provider_claim_lock);
			if (WARN_ON(claim_cookie)) {
				provider_closing = true;
				ret = -EUCLEAN;
				mutex_unlock(&provider_claim_lock);
				goto out;
			}
			active_priv = NULL;
			active_managed = NULL;
			mutex_unlock(&provider_claim_lock);
			platform_set_drvdata(provider, NULL);
			goto out;
		}
		component_registered = true;
	} else {
		if (managed) {
			ret = -EINVAL;
			goto out;
		}
		mutex_lock(&provider_claim_lock);
		provider_closing = true;
		if (claim_quiesce)
			ret = claim_quiesce(claim_cookie);
		mutex_unlock(&provider_claim_lock);
		if (ret)
			goto out; /* Keep descriptor, component and claim on busy/error. */
		if (component_registered) {
			component_del(&provider->dev, &provider_ops);
			component_registered = false;
		}
		mutex_lock(&provider_claim_lock);
		if (WARN_ON(claim_cookie)) {
			ret = -EUCLEAN;
			mutex_unlock(&provider_claim_lock);
			goto out;
		}
		active_priv = NULL;
		active_managed = NULL;
		provider_closing = false;
		mutex_unlock(&provider_claim_lock);
		platform_set_drvdata(provider, NULL);
	}
out:
	mutex_unlock(&provider_lock);
	return ret;
}
EXPORT_SYMBOL(opairshare_set_wonder_managed_priv_data);

int opairshare_set_wonder_priv_data(const void *priv_data)
{
	return opairshare_set_wonder_managed_priv_data(priv_data, NULL);
}
EXPORT_SYMBOL(opairshare_set_wonder_priv_data);

static int __init provider_init(void)
{
	int ret;

	provider = platform_device_alloc(PROVIDER_NAME, PLATFORM_DEVID_NONE);
	if (!provider)
		return -ENOMEM;
	ret = platform_device_add(provider);
	if (ret) {
		platform_device_put(provider);
		provider = NULL;
		return ret;
	}
	pr_info("opairshare_wonder_provider: created %s; stock CNSS untouched\n", PROVIDER_NAME);
	return 0;
}

static void __exit provider_exit(void)
{
	opairshare_set_wonder_priv_data(NULL);
	/* No platform driver remove callback: device destruction has one owner. */
	platform_device_unregister(provider);
	provider = NULL;
}

module_init(provider_init);
module_exit(provider_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("OPAirShare DT-free Wonder provider bridge, independent of CNSS");
