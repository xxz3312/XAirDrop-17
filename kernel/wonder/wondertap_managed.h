/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef WONDERTAP_MANAGED_H
#define WONDERTAP_MANAGED_H

struct module;
/* Private companion, not an extension of the upstream ops/priv ABI. A future
 * backend must bind it explicitly before init. poll_start never resubmits
 * CREATE; retire clears *handle only after actual final resource retirement.
 * The binding owns the callback module until unbind succeeds. No default
 * provider installs these callbacks in 0066.
 */
struct wondertap_managed_ops {
	const struct wondertap_ops *ops;
	struct module *owner;
	int (*poll_start)(void *handle);
	int (*retire)(void **handle);
};
#endif
