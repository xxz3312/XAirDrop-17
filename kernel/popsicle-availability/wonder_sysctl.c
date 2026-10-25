// SPDX-License-Identifier: GPL-2.0
/*
 * Adapted from Leekin2/XAirDrop kmod/wonder_sysctl at
 * eb1fe215c6473a8dbcc6edf6cf1e67d93f250f76.
 * Linux 6.12 register_net_sysctl uses ARRAY_SIZE: no empty sentinel.
 * Default unavailable. A future supervisor must set 1 only after the radio
 * backend and XOS service are ready and clear it on teardown.
 * This module supplies no wireless protocol or firmware support.
 */
#include <linux/module.h>
#include <linux/sysctl.h>
#include <net/net_namespace.h>

static int wonder_enable;
static struct ctl_table_header *wonder_sysctl_header;
static struct ctl_table wonder_sysctl_table[] = {
	{
		.procname = "wonder_enable",
		.data = &wonder_enable,
		.maxlen = sizeof(wonder_enable),
		.mode = 0644,
		.proc_handler = proc_dointvec_minmax,
		.extra1 = SYSCTL_ZERO,
		.extra2 = SYSCTL_ONE,
	},
};

static int __init wonder_sysctl_init(void)
{
	wonder_sysctl_header = register_net_sysctl(&init_net, "net/wonder",
						 wonder_sysctl_table);
	return wonder_sysctl_header ? 0 : -ENOMEM;
}

static void __exit wonder_sysctl_exit(void)
{
	unregister_net_sysctl_table(wonder_sysctl_header);
}

module_init(wonder_sysctl_init);
module_exit(wonder_sysctl_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Xiaomi Share availability bridge; no radio backend");
