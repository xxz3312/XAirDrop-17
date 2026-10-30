# 0061: ML-capable STA default-link registration

0060 phone evidence: register_calls=3, skip_mode=2, skip_ml_adapter=1, register_submitted=0, pe_inserted=0, owner_active=0. PE check calls increased 48 to 65; all three listeners saw zero candidates.

Allow the native STA default vdev registration even when its netdev is marked ML. Continue rejecting subordinate link adapters. Pin the registered default-link pointer and vdev ID with spinlock-protected publication. RX requires the current default link and exact registered vdev identity; reject missing vdev, native link-switch-in-progress, and native wlan_hdd_is_mlo_connection(). This is a legacy-connection experiment, not full MLO support. The native predicate can conservatively reject a link; record hdd_mlo_connection rather than claiming that AP MLO was independently measured.

On unregister, close routing first and deregister the saved vdev ID even if deflink changed. Normal stop/SSR still owns object lifetime; the new owner spinlock protects only publication/snapshot consistency and never spans SME or vdev lookup. Owner/link pointers are compared only, never dereferenced outside native lifetime protection.

Keep global single STA reservation, default-off opt-in, exact Apple type8 prefix, protected/fragment/length/DA checks, original cfg80211 path, and failure quarantine. No firmware filter, monitor, channel switch, off-channel RX, WMA instrumentation or AirDrop success claim.

References: MiCode/vendor_qcom_opensource_wlan@36df473046706a5259942e1bf7222108dbbb860f: wlan_hdd_main.c:4005,10711,11586 and wlan_hdd_p2p.c:1625 native lifecycle/sync; wlan_hdd_main.h deflink and wlan_hdd_is_mlo_connection declaration.

Host fixture executes production owner helper with modeled SME/HDD/spinlocks. It checks ML default acceptance on a modeled legacy link, real MLO/switch/missing-vdev rejection, changed link and reused vdev rejection, saved-ID unregister, single owner, SSR replay, post failures and shutdown quarantine. Full locking/concurrency and firmware require device validation.
