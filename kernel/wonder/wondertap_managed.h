/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef WONDERTAP_MANAGED_H
#define WONDERTAP_MANAGED_H

struct module;
/* Private companion, not an extension of the upstream ops/priv ABI. A future
 * backend must bind it explicitly before init. poll_start never resubmits
 * CREATE; retire clears *handle only after actual final resource retirement.
 * The binding owns the callback module until unbind succeeds. The 0067 private
 * provider transports these callbacks; radio activation is still disabled.
 */
struct wondertap_managed_ops {
	const struct wondertap_ops *ops;
	struct module *owner;
	int (*poll_start)(void *handle);
	int (*retire)(void **handle);
};

enum wondertap_provider_command {
	WONDERTAP_PROVIDER_QUERY,
	WONDERTAP_PROVIDER_CLAIM,
	WONDERTAP_PROVIDER_RELEASE,
};
/* Private side channel; upstream ops/priv layouts remain unchanged. The caller
 * holds the provider module reference through RELEASE. Cookie memory and the
 * quiesce callback remain live until RELEASE returns. Quiesce must not call
 * provider/component APIs; it only fences admission and checks local ownership.
 */
typedef int (*wondertap_provider_control_fn)(enum wondertap_provider_command,
	const void *priv, void *cookie, int (*quiesce)(void *),
	const struct wondertap_managed_ops **managed);
int opairshare_set_wonder_managed_priv_data(const void *priv,
						const struct wondertap_managed_ops *managed);
int opairshare_wonder_managed_control(enum wondertap_provider_command command,
		const void *priv, void *cookie, int (*quiesce)(void *),
		const struct wondertap_managed_ops **managed);
#endif
