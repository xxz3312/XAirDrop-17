// SPDX-License-Identifier: GPL-2.0-only
/* Private managed binding transport; radio activation remains unsupported. */
#include <linux/errno.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/string.h>
#include "wlan_hdd_main.h"
#include "wlan_hdd_trace.h"
#include "wlan_hdd_mishare_wonder_api.h"
#include "wlan_hdd_mishare_backend.h"
#include "wlan_hdd_mishare_managed.h"

/* Strong private provider dependency: cannot silently bind to stock CNSS. */
extern int opairshare_set_wonder_managed_priv_data(const void *priv_data,
						 const struct wondertap_managed_ops *managed);
static bool mishare_wonder_attach;
module_param(mishare_wonder_attach, bool, 0444);
MODULE_PARM_DESC(mishare_wonder_attach,
				"Opt-in typed Wonder table binding only; no radio backend yet");
static DEFINE_MUTEX(mishare_backend_lock);
static struct hdd_context *mishare_backend_owner;
static bool mishare_backend_closing;

/* Binding can synchronously query this table while registration holds the
 * owner mutex. Callbacks never take that mutex or dereference HDD context.
 */
static int mishare_backend_init(void **handle, const struct wondertap_init_params *params)
{
	if (!handle)
		return -EINVAL;
	*handle = NULL;
	if (!params)
		return -EINVAL;
	return -EOPNOTSUPP;
}
static void mishare_backend_deinit(void *handle, const struct wondertap_deinit_params *params)
{
	/* init never publishes a handle; there is no host/radio resource to free. */
	(void)handle;
	(void)params;
}
static int mishare_backend_freq(void *handle, const struct wondertap_set_freq_params *params)
{
	(void)handle;
	(void)params;
	return -EOPNOTSUPP;
}
static int mishare_backend_filter(void *handle, enum wondertap_filter_type type, const void *params)
{
	(void)handle;
	(void)type;
	(void)params;
	return -EOPNOTSUPP;
}
static int mishare_backend_rate(void *handle, const struct wondertap_fixed_tx_rate_params *params)
{
	(void)handle;
	(void)params;
	return -EOPNOTSUPP;
}
static int mishare_backend_mask(void *handle, const struct wondertap_tx_rate_mask_params *params)
{
	(void)handle;
	(void)params;
	return -EOPNOTSUPP;
}
static int mishare_backend_capabilities(void *handle, struct wondertap_capability *features)
{
	(void)handle;
	if (!features)
		return -EINVAL;
	memset(features, 0, sizeof(*features));
	return 0;
}
static const struct wondertap_ops mishare_backend_ops = {
	.init = mishare_backend_init,
	.deinit = mishare_backend_deinit,
	.set_freq = mishare_backend_freq,
	.set_filter = mishare_backend_filter,
	.set_fixed_tx_rate = mishare_backend_rate,
	.set_tx_rate_mask = mishare_backend_mask,
	.get_capabilities = mishare_backend_capabilities,
};
/* These callbacks intentionally cannot allocate or activate a radio session.
 * They make the metadata binding use the real managed transport. Replacing
 * init requires the native parent lease and qualified SSR/remove retirement.
 */
static int mishare_backend_poll_start(void *handle)
{
	return handle ? -EOPNOTSUPP : -EINVAL;
}
static int mishare_backend_retire(void **handle)
{
	if (!handle)
		return -EINVAL;
	return *handle ? -EOPNOTSUPP : 0;
}
static const struct wondertap_managed_ops mishare_backend_managed = {
	.ops = &mishare_backend_ops,
	.owner = THIS_MODULE,
	.poll_start = mishare_backend_poll_start,
	.retire = mishare_backend_retire,
};
static const struct wondertap_priv mishare_backend_priv = {
	.ver = WONDER_VERSION_1_4_1,
	.wonder_ops = &mishare_backend_ops,
};

int mishare_wonder_backend_register(struct hdd_context *hdd)
{
	int ret = 0;

	if (!hdd)
		return -EINVAL;
	if (!mishare_wonder_attach)
		return 0;
	mutex_lock(&mishare_backend_lock);
	if (mishare_backend_owner) {
		ret = mishare_backend_closing ? -ESHUTDOWN :
			  mishare_backend_owner == hdd ? 0 : -EBUSY;
		goto unlock;
	}
	ret = opairshare_set_wonder_managed_priv_data(&mishare_backend_priv,
												   &mishare_backend_managed);
	if (!ret)
		mishare_backend_owner = hdd;
unlock:
	mutex_unlock(&mishare_backend_lock);
	return ret;
}

int mishare_wonder_backend_unregister(struct hdd_context *hdd)
{
	int ret = 0;

	if (!hdd)
		return 0;
	mutex_lock(&mishare_backend_lock);
	if (mishare_backend_owner == hdd) {
		mishare_backend_closing = true;
		ret = opairshare_set_wonder_managed_priv_data(NULL, NULL);
		if (ret)
			hdd_err("MiShare managed detach retained owner: %d", ret);
		else {
			mishare_backend_owner = NULL;
			mishare_backend_closing = false;
		}
	}
	mutex_unlock(&mishare_backend_lock);
	return ret;
}
