/* SPDX-License-Identifier: GPL-2.0-only */
#include <linux/errno.h>
#include <linux/module.h>
#include "wondertap_internal.h"

/* Target GKI does not export __symbol_get/put. The popsicle build uses a
 * normal module dependency on the private provider; generic builds keep the
 * original synchronous interface with no provider dependency.
 */
static wondertap_provider_control_fn wondertap_control_get(void)
{
#ifdef WONDER_PRIVATE_MANAGED_PROVIDER
	return opairshare_wonder_managed_control;
#else
	return NULL;
#endif
}

static int wondertap_provider_quiesce(void *cookie)
{
	/* No provider/component calls while the provider's claim mutex is held. */
	return wondertap_quiesce_managed(cookie);
}

int wondertap_provider_bind(struct wondertap_data *w, const void *priv)
{
	wondertap_provider_control_fn control;
	const struct wondertap_managed_ops *managed = NULL;
	int ret;

	control = wondertap_control_get();
	if (!control)
		return wondertap_activate_legacy(w);
	ret = control(WONDERTAP_PROVIDER_QUERY, priv, NULL, NULL, &managed);
	if (ret == -EOPNOTSUPP) {
		return wondertap_activate_legacy(w);
	}
	if (ret)
		goto put;
	ret = wondertap_bind_managed_staged(w, managed);
	if (ret)
		goto put;
	ret = control(WONDERTAP_PROVIDER_CLAIM, priv, w,
		      wondertap_provider_quiesce, NULL);
	if (ret) {
		wondertap_quiesce_managed(w); /* Staged init cannot own resources. */
		goto put;
	}
	ret = wondertap_activate_managed(w);
	if (ret) {
		wondertap_quiesce_managed(w);
		control(WONDERTAP_PROVIDER_RELEASE, priv, w, NULL, NULL);
		goto put;
	}
	w->managed_provider_control = control;
	w->managed_provider_priv = priv;
	return 0; /* The loader holds the strong private provider dependency. */
put:
	return ret;
}

int wondertap_provider_unbind(struct wondertap_data *w)
{
	wondertap_provider_control_fn control = w->managed_provider_control;
	int ret;

	if (!control)
		return 0;
	ret = wondertap_quiesce_managed(w);
	if (ret)
		return ret;
	ret = control(WONDERTAP_PROVIDER_RELEASE, w->managed_provider_priv,
		      w, NULL, NULL);
	if (ret)
		return ret;
	w->managed_provider_control = NULL;
	w->managed_provider_priv = NULL;
	return 0;
}
