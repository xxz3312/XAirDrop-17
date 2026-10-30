# 0062: WMA / management dispatcher / PE ingress diagnostics

0061 phone confirmed register_ml_default=1, register_submitted=1, pe_add_seen=1, pe_inserted=1, owner_active=1. Three listeners saw no candidates; pe_check_calls increased 8 to 15 while pe_apple and hdd_calls remained zero.

Keep 0061 owner policy unchanged. Add numeric counters to native wma_mgmt_rx_process, tgt_mgmt_txrx_rx_frame_handler and pre-registration portions of lim_handle80211_frames. No filter, scheduling, callback, buffer ownership, parser or return status change. Shared bounded header classifier only reads validated owned frame bytes, not the opaque WMI event. WMA classifies after native endian copy; dispatcher captures a numeric ingress tag before simulation/ownership transfer; callback-attempt counters use that saved tag, never inspect consumed buffers.

WMA fields: event entry, handle/parameter allocation/extraction/native buffer validation/allocation failures, prepared frame counts, Action/category127/Apple type8 prefixes and over256 prefix frames, missing psoc, downstream return success/failure and prefix-tagged failures. Success only reports mgmt_txrx_rx_handler returned success, not PE or userspace delivery.

Dispatcher fields: ingress and prefix frames, non-management/control type, invalid source+BSSID addresses, protected short length, unspecified frame type, simulation rejection, handler-list allocation, absent callback, beacon rate limit, clone failure and callback attempts for original prefix-tagged frames. Some reasons are all-traffic counts; only names containing apple are prefix-specific. Callback attempts count each component callback including clones, not unique packets or proof of PE delivery.

PE fields: handle80211 entry/prefix and CAC, extscan/epno bypass, no-session exits, plus packet-info extraction failure. Existing registered-frame match counters remain. EXTSCAN counts a bypass from the normal matching path, not necessarily complete packet loss; beacon/probe may already be handled separately. Repeated/deferred/reordered processing and multiple callbacks prevent naive cross-layer count equality. WMA MLO metadata-only event and every pre-WMA/reorder/scheduler path are not individually instrumented.

All counters are opt-in module-lifetime, cross-interface, individually atomic but not an atomic snapshot. Classification supports 24..2304 bytes and Apple prefix at fixed 24-byte management header offset, with minimum29 bytes. It does not authenticate Apple or parse AWDL TLVs, nor classify protected/HT-control layout variants as full protocol support. No frame bytes/MAC/SSID are newly stored. Logs retain existing native device data.

Host production helper fixture validates shared prefix boundaries at exact buffer lengths and worst-case 64-bit sysfs dump size. It does not execute the full native WMA/dispatcher/PE runtime; CI compiles and strictly links the actual patched files. Phone evidence still required.
