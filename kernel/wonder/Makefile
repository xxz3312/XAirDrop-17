obj-m += wonder.o
# Stock popsicle mac80211 is an external module with its own wireless config.
# The GKI /proc/config.gz has CFG80211 disabled and omits these ABI switches.
# Keep the override local to Wonder; never rewrite the running kernel config.
ifeq ($(POPSICLE_STOCK_MAC80211_ABI),1)
ccflags-y += -DCONFIG_NL80211_TESTMODE=1
ccflags-y += -include $(src)/popsicle_mac80211_abi.h
endif

wonder-y := main.o mac80211.o wondertap.o nl80211_ven_cmd.o mac80211_txs.o ssr.o band_config.o

ifneq ($(CONFIG_DEBUG_FS),)
wonder-y += debugfs.o
endif

all:
	make -C /lib/modules/$(shell uname -r)/build M=$(PWD) modules

clean:
	make -C /lib/modules/$(shell uname -r)/build M=$(PWD) clean
