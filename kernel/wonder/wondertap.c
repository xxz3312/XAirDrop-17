#define LOG_MODULE_NAME "wondertap"

#include <linux/errno.h>
#include <linux/export.h>
#include <linux/module.h>
#include <linux/etherdevice.h>
#include <linux/delay.h>
#include <linux/ieee80211.h>

#include "include/wonder/wondertap.h"
#include "wondertap_internal.h"
#include "wonder_log.h"

static const struct wondertap_ops *wondertap_ops = NULL;

/* Per-instance lock protects these explicit managed bindings. The caller must
 * still retain native parents; module refs protect text, not HDD/psoc memory.
 */
static int wondertap_bind_managed_mode(struct wondertap_data *w,
				const struct wondertap_managed_ops *managed, bool staged)
{
	int ret = 0;
	if (!w || !managed || !managed->ops || !managed->ops->init ||
		!managed->owner || !managed->poll_start || !managed->retire)
		return -EINVAL;
	if (wonder_external_monitor)
		return -EOPNOTSUPP;
	mutex_lock(&w->lock);
	if (w->managed_bound || w->recovery_in_progress ||
		w->state != WONDERTAP_STATE_DOWN || w->vendor_handle)
		ret = -EBUSY;
	else if (managed->ops != wondertap_ops)
		ret = -ENODEV;
	else if (!try_module_get(managed->owner))
		ret = -ENODEV;
	else {
		w->managed = *managed;
		w->managed_bound = true;
		w->managed_quiescing = staged;
		w->managed_activation_pending = staged;
		w->managed_caps_valid = false;
		w->managed_error = 0;
	}
	mutex_unlock(&w->lock);
	return ret;
}

bool wondertap_fence_managed(struct wondertap_data *w)
{
	bool held;
	mutex_lock(&w->lock);
	held = w->managed_bound || w->managed_provider_control ||
	       w->managed_instance_pin || w->managed_quiescing;
	if (held) {
		w->managed_quiescing = true;
		w->managed_activation_pending = false;
	}
	mutex_unlock(&w->lock);
	return held;
}

bool wondertap_recovery_begin(struct wondertap_data *w)
{
	bool admitted = false;
	mutex_lock(&w->lock);
	if (w->managed_bound || w->managed_provider_control ||
	    w->managed_instance_pin || w->managed_quiescing) {
		w->managed_quiescing = true;
		w->managed_activation_pending = false;
	} else if (!w->recovery_in_progress) {
		w->recovery_in_progress = true;
		admitted = true;
	}
	mutex_unlock(&w->lock);
	return admitted;
}
void wondertap_recovery_end(struct wondertap_data *w)
{
	mutex_lock(&w->lock);
	w->recovery_in_progress = false;
	mutex_unlock(&w->lock);
}

int wondertap_provider_prepare(struct wondertap_data *w)
{
	int ret = 0;
	mutex_lock(&w->lock);
	if (w->managed_bound || w->managed_provider_control || w->recovery_in_progress ||
		w->state != WONDERTAP_STATE_DOWN || w->vendor_handle ||
		w->managed_instance_pin)
		ret = -EBUSY;
	else
		w->managed_quiescing = true;
	mutex_unlock(&w->lock);
	return ret;
}
int wondertap_activate_legacy(struct wondertap_data *w)
{
	int ret = 0;
	mutex_lock(&w->lock);
	if (w->managed_bound || w->vendor_handle || w->managed_instance_pin ||
		w->state != WONDERTAP_STATE_DOWN)
		ret = -EBUSY;
	else
		w->managed_quiescing = false;
	mutex_unlock(&w->lock);
	return ret;
}

int wondertap_bind_managed(struct wondertap_data *w,
						  const struct wondertap_managed_ops *managed)
{
	return wondertap_bind_managed_mode(w, managed, false);
}
int wondertap_bind_managed_staged(struct wondertap_data *w,
								 const struct wondertap_managed_ops *managed)
{
	return wondertap_bind_managed_mode(w, managed, true);
}
int wondertap_activate_managed(struct wondertap_data *w)
{
	int ret = 0;
	mutex_lock(&w->lock);
	if (!w->managed_bound || !w->managed_activation_pending ||
		w->state != WONDERTAP_STATE_DOWN ||
		w->vendor_handle || w->managed_instance_pin)
		ret = -EBUSY;
	else {
		w->managed_quiescing = false;
		w->managed_activation_pending = false;
	}
	mutex_unlock(&w->lock);
	return ret;
}
int wondertap_quiesce_managed(struct wondertap_data *w)
{
	mutex_lock(&w->lock);
	w->managed_quiescing = true;
	w->managed_activation_pending = false;
	mutex_unlock(&w->lock);
	return wondertap_unbind_managed(w);
}

int wondertap_unbind_managed(struct wondertap_data *w)
{
	struct module *owner = NULL;
	int ret = 0;
	if (!w)
		return -EINVAL;
	mutex_lock(&w->lock);
	if (w->managed_bound) {
		if (w->state != WONDERTAP_STATE_DOWN || w->vendor_handle ||
			w->managed_instance_pin)
			ret = -EBUSY;
		else {
			owner = w->managed.owner;
			memset(&w->managed, 0, sizeof(w->managed));
			w->managed_bound = false;
			w->managed_caps_valid = false;
			w->managed_error = 0;
		}
	}
	mutex_unlock(&w->lock);
	if (owner)
		module_put(owner);
	return ret;
}

static bool wondertap_transition_pending(struct wondertap_data *w)
{
	return w->recovery_in_progress || w->managed_quiescing || w->state == WONDERTAP_STATE_STARTING ||
		   w->state == WONDERTAP_STATE_DRAINING ||
		   w->state == WONDERTAP_STATE_BLOCKED ||
		   (w->managed_bound && w->state == WONDERTAP_STATE_DOWN &&
			(w->vendor_handle || w->managed_instance_pin));
}

static void wondertap_managed_unpin(struct wondertap_data *w)
{
	if (w->managed_instance_pin) {
		w->managed_instance_pin = false;
		module_put(THIS_MODULE);
	}
}

/* Called after exactly one init/poll submission under the instance lock. */
static int wondertap_managed_started(struct wondertap_data *w, int ret)
{
	if (ret == 0 || ret == -EINPROGRESS) {
		if (!w->vendor_handle) {
			w->state = WONDERTAP_STATE_BLOCKED;
			w->managed_error = -EUCLEAN;
			return -EUCLEAN;
		}
		w->state = ret ? WONDERTAP_STATE_STARTING : WONDERTAP_STATE_UP;
		return ret;
	}
	w->managed_error = ret;
	if (w->vendor_handle)
		w->state = WONDERTAP_STATE_DRAINING;
	else {
		w->state = WONDERTAP_STATE_DOWN;
		wondertap_managed_unpin(w);
	}
	return ret;
}

static int wondertap_retire_locked(struct wondertap_data *w)
{
	void *next;
	int ret;
	if (!w->managed_bound)
		return -EOPNOTSUPP;
	if (w->state == WONDERTAP_STATE_BLOCKED)
		return w->managed_error ? w->managed_error : -EUCLEAN;
	if (w->state == WONDERTAP_STATE_DOWN && !w->vendor_handle)
		return 0;
	if (!w->vendor_handle) {
		w->state = WONDERTAP_STATE_BLOCKED;
		w->managed_error = -EUCLEAN;
		return -EUCLEAN;
	}
	w->state = WONDERTAP_STATE_DRAINING;
	next = w->vendor_handle;
	ret = w->managed.retire(&next);
	if (!ret && !next) {
		w->vendor_handle = NULL;
		w->state = WONDERTAP_STATE_DOWN;
		w->managed_error = 0;
		wondertap_managed_unpin(w);
		return 0;
	}
	if (ret == -EINPROGRESS && next == w->vendor_handle)
		return ret;
	/* A changed pointer or false success cannot authorize another callback on
	 * possibly freed storage. Retain the original opaque token and pins; never
	 * dereference it on the blocked path. Parent teardown remains forbidden.
	 */
	w->state = WONDERTAP_STATE_BLOCKED;
	w->managed_error = next != w->vendor_handle || !ret ? -EUCLEAN : ret;
	return w->managed_error;
}

int wondertap_retire(struct wondertap_data *w)
{
	int ret;
	if (!w)
		return -EINVAL;
	mutex_lock(&w->lock);
	ret = wondertap_retire_locked(w);
	mutex_unlock(&w->lock);
	return ret;
}

static bool wondertap_is_up(struct wondertap_data *wondertap)
{
	return wondertap->state == WONDERTAP_STATE_UP;
}

int wondertap_register_ops(const struct wondertap_ops *ops)
{
	if (!ops) {
		wonder_error("Attempted to register with NULL ops\n");
		return -EINVAL;
	}

	if (wondertap_ops) {
		wonder_warn("Overwriting existing vendor operations pointer\n");
	}

	wondertap_ops = ops;
	wonder_info("Registered new vendor operations\n");

	return 0;
}

void wondertap_unregister_ops(const struct wondertap_ops *ops)
{
	if (wondertap_ops == ops) {
		wondertap_ops = NULL;
		wonder_info("Unregistered vendor operations.\n");
	} else {
		wonder_warn("Attempted to unregister with an incorrect ops pointer.\n");
	}
}

static void wondertap_dump_init_params(struct wondertap_init_params *params)
{
	wonder_info("========== [ Wondertap Vendor Init ] ==========\n");
	wonder_info("    Channel: Freq=%u, Bw=%u\n", params->channel.freq,
		params->channel.bandwidth);
	if (params->rate_adaptation_enable) {
		wonder_info("RA TxRate: Max Pre=%u, Max Mcs=%u, Max Bw=%u, Max Nss=%u\n",
				params->tx_rate_mask.max_preamble,
				params->tx_rate_mask.max_mcs,
				params->tx_rate_mask.max_bw,
				params->tx_rate_mask.max_nss);
	} else {
		wonder_info("    Fixed TxRate:  Pre=%u, Mcs=%u, Gi=%u, Bw=%u\n",
				params->tx_rate.preamble,
				params->tx_rate.mcs,
				params->tx_rate.gi,
				params->tx_rate.bw);
	}
	wonder_info("    Country: %.2s\n", params->country_code);
	wonder_info("    MAC: %02x:XX:XX:XX:XX:%02x\n", params->mac_addr[0],
		params->mac_addr[5]);
	wonder_info("    BSSID: %02x:XX:XX:XX:XX:%02x\n", params->bssid[0], params->bssid[5]);
	wonder_info("===============================================\n");
}

int wondertap_init(struct wondertap_data *wondertap, const struct wondertap_init_params *_params)
{
	struct wondertap_init_params params = {};
	int ret = -EOPNOTSUPP;
	const struct wondertap_ops *ops;

	if (!wondertap || !_params)
		return -EINVAL;
	mutex_lock(&wondertap->lock);
	if (wondertap->recovery_in_progress) {
		mutex_unlock(&wondertap->lock);
		return -EBUSY;
	}
	if (wondertap->managed_quiescing) {
		mutex_unlock(&wondertap->lock);
		return -ESHUTDOWN;
	}
	ops = wondertap->managed_bound ? wondertap->managed.ops : wondertap_ops;
	if (wondertap->managed_bound) {
		if (wondertap->managed.ops != wondertap_ops) {
			ret = -ENODEV;
			goto out;
		}
		if (wondertap->state == WONDERTAP_STATE_STARTING) {
			ret = wondertap_managed_started(wondertap,
				wondertap->managed.poll_start(wondertap->vendor_handle));
			goto out;
		}
		if (wondertap_transition_pending(wondertap)) {
			ret = -EBUSY;
			goto out;
		}
	}
	if (wondertap_is_up(wondertap)) {
		wonder_warn("Already initialized\n");
		ret = -EBUSY;
		goto out;
	}

	if (!((wondertap->cache_flags & WONDERTAP_CACHE_FREQ_SET) &&
		(wondertap->cache_flags & WONDERTAP_CACHE_TX_RATE_SET) &&
		(wondertap->cache_flags & WONDERTAP_CACHE_BSSID_SET) &&
		(wondertap->cache_flags & WONDERTAP_CACHE_COUNTRY_CODE_SET))) {
		wonder_error("Init failed: Missing cached settings. flags=0x%x\n",
						wondertap->cache_flags);
		ret = -EINVAL;
		goto out;
	}

	if (ops && ops->init) {
		eth_random_addr(wondertap->mac_addr);
		params.channel = wondertap->cached_freq;
		params.tx_rate = wondertap->cached_tx_rate;
		memcpy(params.bssid, wondertap->cached_bssid, ETH_ALEN);
		memcpy(params.mac_addr, wondertap->mac_addr, ETH_ALEN);
		memcpy(params.country_code, wondertap->cached_country_code, sizeof(wondertap->cached_country_code));

		params.ampdu_enable = _params->ampdu_enable;
		params.amsdu_enable = _params->amsdu_enable;
		params.mgmt_retry_limit = _params->mgmt_retry_limit;
		params.data_retry_limit = _params->data_retry_limit;
		if (_params->rate_adaptation_enable) {
			params.rate_adaptation_enable = _params->rate_adaptation_enable;
			params.tx_rate_mask.max_preamble = wondertap->cached_tx_rate.preamble;
			params.tx_rate_mask.max_bw = wondertap->cached_tx_rate.bw;
			params.tx_rate_mask.max_nss = wondertap->cached_tx_rate.nss;
			params.tx_rate_mask.max_mcs = wondertap->cached_tx_rate.mcs;
		}

		wondertap_dump_init_params(&params);
		/* Initialization failure is returned; no blind hardware retries. */
		if (wondertap->managed_bound) {
			if (!try_module_get(THIS_MODULE)) {
				ret = -ENODEV;
				goto out;
			}
			wondertap->managed_instance_pin = true;
			wondertap->managed_error = 0;
		}
		ret = ops->init(&wondertap->vendor_handle, &params);
		if (wondertap->managed_bound) {
			ret = wondertap_managed_started(wondertap, ret);
			goto out;
		}
		if (ret == 0) {
			wondertap->state = WONDERTAP_STATE_UP;
			wonder_info("Vendor init successful. State set to UP.\n");
		} else {
			wonder_error("Vendor init failed: %d\n", ret);
			goto out;
		}
	} else {
		wonder_error("Vendor operation 'init' is not implemented\n");
		ret = -EOPNOTSUPP;
	}

out:
	mutex_unlock(&wondertap->lock);
	return ret;
}

void wondertap_deinit(struct wondertap_data *wondertap)
{
	struct wondertap_deinit_params params;

	mutex_lock(&wondertap->lock);
	if (wondertap->managed_quiescing && !wondertap->managed_bound) {
		mutex_unlock(&wondertap->lock);
		return;
	}
	if (wondertap->managed_bound) {
		int ret = wondertap_retire_locked(wondertap);
		if (ret)
			wonder_error("Managed retirement retained instance: %d\n", ret);
		mutex_unlock(&wondertap->lock);
		return;
	}
	if (wondertap_ops && wondertap_ops->deinit) {
		memset(&params, 0, sizeof(params));
		memcpy(params.country_code, wondertap->cached_country_code, sizeof(wondertap->cached_country_code));
		wonder_info("========== [ Wondertap Vendor Deinit ] ==========\n");
		wonder_info("    Country: %.2s\n", params.country_code);
		wonder_info("=================================================\n");
		wondertap_ops->deinit(wondertap->vendor_handle, &params);
		/* Legacy deinit is synchronous: do not leave a retired token behind. */
		wondertap->vendor_handle = NULL;
	} else {
		wonder_error("Vendor operation 'deinit' is not implemented\n");
	}
	wondertap->state = WONDERTAP_STATE_DOWN;
	mutex_unlock(&wondertap->lock);
}

int wondertap_set_freq(struct wondertap_data *wondertap, const struct wondertap_set_freq_params *params)
{
	int ret = -EOPNOTSUPP;
	const struct wondertap_ops *ops;

	if (wonder_external_monitor)
		return -EOPNOTSUPP;

	mutex_lock(&wondertap->lock);
	ops = wondertap->managed_bound ? wondertap->managed.ops : wondertap_ops;
	if (wondertap_transition_pending(wondertap)) {
		mutex_unlock(&wondertap->lock);
		return -EBUSY;
	}

	if (wondertap_is_up(wondertap)) {
		if (wondertap->cached_freq.freq == params->freq &&
		    wondertap->cached_freq.bandwidth == params->bandwidth) {
			ret = 0; /* Already on this successfully cached channel. */
		} else if (ops && ops->set_freq) {
			ret = ops->set_freq(wondertap->vendor_handle, params);
		} else {
			wonder_error("Vendor operation 'set_freq' is not implemented\n");
			ret = -EOPNOTSUPP;
		}
	} else {
		wonder_warn("wondertap is not active; caching incoming channel settings.\n");
		ret = 0;
	}
	if (!ret) {
		wondertap->cached_freq = *params;
		wondertap->cache_flags |= WONDERTAP_CACHE_FREQ_SET;
	}

	mutex_unlock(&wondertap->lock);
	return ret;
}

int wondertap_set_filter(struct wondertap_data *wondertap, enum wondertap_filter_type filter_type,
			 const void *params)
{
	int ret = -EOPNOTSUPP;
	const struct wondertap_ops *ops;

	if (wonder_external_monitor) {
		const struct wondertap_frame_filter_params *filter = params;
		u32 value = 0;

		if (filter_type != WONDERTAP_FILTER_TYPE_FRAME)
			return -EOPNOTSUPP;
		if (!filter)
			return -EINVAL;
		if (filter->enabled) {
			if ((filter->frame_type != IEEE80211_FTYPE_MGMT &&
			     filter->frame_type != IEEE80211_FTYPE_CTL &&
			     filter->frame_type != IEEE80211_FTYPE_DATA) ||
			    (filter->frame_subtype & ~IEEE80211_FCTL_STYPE))
				return -EINVAL;
			value = BIT(31) | filter->frame_type | filter->frame_subtype;
		}
		WRITE_ONCE(wondertap->rx_frame_filter, value);
		return 0;
	}

	mutex_lock(&wondertap->lock);
	ops = wondertap->managed_bound ? wondertap->managed.ops : wondertap_ops;
	if (wondertap_is_up(wondertap)) {
		if (ops && ops->set_filter) {
			ret = ops->set_filter(wondertap->vendor_handle,
				filter_type, params);
		} else {
			wonder_error("Vendor operation 'set_filter' is not implemented\n");
			ret = -EOPNOTSUPP;
		}
	} else {
		wonder_error("wondertap is invalid or not up.\n");
		ret = -ENODEV;
	}

	mutex_unlock(&wondertap->lock);
	return ret;
}

int wondertap_set_fixed_tx_rate(struct wondertap_data *wondertap, const struct wondertap_fixed_tx_rate_params *params)
{
	int ret = -EOPNOTSUPP;
	const struct wondertap_ops *ops;

	if (wonder_external_monitor)
		return -EOPNOTSUPP;

	mutex_lock(&wondertap->lock);
	ops = wondertap->managed_bound ? wondertap->managed.ops : wondertap_ops;
	if (wondertap_transition_pending(wondertap)) {
		mutex_unlock(&wondertap->lock);
		return -EBUSY;
	}

	wondertap->cached_tx_rate = *params;
	wondertap->cache_flags |= WONDERTAP_CACHE_TX_RATE_SET;
	if (wondertap_is_up(wondertap)) {
		if (ops && ops->set_fixed_tx_rate) {
			ret = ops->set_fixed_tx_rate(wondertap->vendor_handle, params);
		} else {
			wonder_error("Vendor operation 'set_fixed_tx_rate' is not implemented\n");
			ret = -EOPNOTSUPP;
		}
	} else {
		wonder_warn("wondertap is not active; caching incoming fixed TX rate settings.\n");
		ret = 0;
	}

	mutex_unlock(&wondertap->lock);
	return ret;
}

int wondertap_set_tx_rate_mask(struct wondertap_data *wondertap, const struct wondertap_tx_rate_mask_params *params)
{
	int ret = -EOPNOTSUPP;
	const struct wondertap_ops *ops;

	if (wonder_external_monitor)
		return -EOPNOTSUPP;

	mutex_lock(&wondertap->lock);
	ops = wondertap->managed_bound ? wondertap->managed.ops : wondertap_ops;
	if (wondertap_transition_pending(wondertap)) {
		mutex_unlock(&wondertap->lock);
		return -EBUSY;
	}

	wondertap->cached_tx_rate.preamble = params->max_preamble;
	wondertap->cached_tx_rate.mcs = params->max_mcs;
	wondertap->cached_tx_rate.bw = params->max_bw;
	wondertap->cached_tx_rate.nss = params->max_nss;
	wondertap->cached_tx_rate.gi = WONDERTAP_RATE_GI_DEFAULT;
	wondertap->cache_flags |= WONDERTAP_CACHE_TX_RATE_SET;
	if (wondertap_is_up(wondertap)) {
		if (ops && ops->set_tx_rate_mask) {
			ret = ops->set_tx_rate_mask(wondertap->vendor_handle, params);
		} else {
			wonder_error("Vendor operation 'set_tx_rate_mask' is not implemented\n");
			ret = -EOPNOTSUPP;
		}
	} else {
		wonder_warn("wondertap is not active; caching incoming TX rate settings.\n");
		ret = -ENODEV;
	}

	mutex_unlock(&wondertap->lock);
	return ret;
}

int wondertap_set_reg(struct wondertap_data *wondertap, const char *country_code)
{
	mutex_lock(&wondertap->lock);
	if (wondertap_transition_pending(wondertap)) {
		mutex_unlock(&wondertap->lock);
		return -EBUSY;
	}


	memcpy(wondertap->cached_country_code, country_code, sizeof(wondertap->cached_country_code));
	wondertap->cache_flags |= WONDERTAP_CACHE_COUNTRY_CODE_SET;

	wonder_error("Update country code=%s\n", wondertap->cached_country_code);

	mutex_unlock(&wondertap->lock);

	return 0;
}

int wondertap_get_capabilities(struct wondertap_data *wondertap, struct wondertap_capability *features)
{
	if (!features)
		return -EINVAL;
	if (wonder_external_monitor) {
		if (!features)
			return -EINVAL;
		memset(features, 0, sizeof(*features));
		features->bits.frame_type_filter = 1;
		return 0;
	}
	mutex_lock(&wondertap->lock);
	if (wondertap->recovery_in_progress) {
		mutex_unlock(&wondertap->lock);
		return -EBUSY;
	}
	if (wondertap->managed_quiescing) {
		mutex_unlock(&wondertap->lock);
		return -ESHUTDOWN;
	}
	if (wondertap->managed_bound) {
		const struct wondertap_ops *ops = wondertap->managed.ops;
		int ret;
		if (wondertap->state == WONDERTAP_STATE_STARTING &&
			wondertap->managed_caps_valid) {
			*features = wondertap->managed_caps;
			mutex_unlock(&wondertap->lock);
			return 0;
		}
		if (wondertap_transition_pending(wondertap)) {
			mutex_unlock(&wondertap->lock);
			return -EBUSY;
		}
		ret = ops->get_capabilities ?
			ops->get_capabilities(wondertap->vendor_handle, features) : -EOPNOTSUPP;
		if (!ret) {
			wondertap->managed_caps = *features;
			wondertap->managed_caps_valid = true;
		}
		mutex_unlock(&wondertap->lock);
		return ret;
	}
	mutex_unlock(&wondertap->lock);
	if (wondertap_ops && wondertap_ops->get_capabilities) {
		return wondertap_ops->get_capabilities(wondertap->vendor_handle, features);
	}

	wonder_error("Vendor operation 'get_capabilities' is not implemented\n");
	return -EOPNOTSUPP;
}

int wondertap_get_interface_mac_address(struct wondertap_data *wondertap, u8 (*mac_addr)[ETH_ALEN])
{
	int ret = -EOPNOTSUPP;

	mutex_lock(&wondertap->lock);
	if (wondertap_is_up(wondertap)) {
		memcpy(*mac_addr, wondertap->mac_addr, sizeof(u8) * ETH_ALEN);
		ret = 0;
	} else {
		wonder_error("wondertap is invalid or not up.\n");
		ret = -ENODEV;
	}

	mutex_unlock(&wondertap->lock);
	return ret;
}

int wondertap_set_bssid_filter(struct wondertap_data *wondertap, const u8 *bssid)
{
	mutex_lock(&wondertap->lock);
	if (wondertap_transition_pending(wondertap)) {
		mutex_unlock(&wondertap->lock);
		return -EBUSY;
	}

	memcpy(wondertap->cached_bssid, bssid, sizeof(u8) * ETH_ALEN);
	wondertap->cache_flags |= WONDERTAP_CACHE_BSSID_SET;
	wonder_warn("Caching incoming BSSID filter settings.\n");
	mutex_unlock(&wondertap->lock);
	return 0;
}
