# 0099 Production HTT peer-unmap parser and indication ownership

Implementation prepared; unified Actions compilation/validation pending.

Patch 0037 adds `dp_htt_t2h_peer_unmap_try_handle()` to the production WLAN
`dp_htt.c`. The existing HTC receive handler invokes it before accessing the
packet context or header. It consumes transport errors, cancellation, absent
context/buffer/data, and short headers. Successful non-unmap messages return to
the existing generic dispatcher with buffer ownership intact. Recognized unmaps
are checked before field access, delivered to the original native DP handler,
and their indication nbuf is freed exactly once after delivery.

V1 requires its four-byte prefix. V2 requires the twenty-byte consumed prefix
through `PEER_WDS_FREE_COUNT`, rather than requiring all twenty-eight bytes of
the current wire format; this preserves the previous consumer's trailing-field
compatibility. A bounded copy into aligned local words uses the original wire
GET macros and original MAC deswizzle. The old two switch arms are removed;
unselected switch arms and the existing HTC receive registration are retained.
Other HTT payload formats are not validated by this change.

The new host fixture executes the exact production helper and the original
MAC deswizzle with an independent literal wire encoder. The 152 prior composite
selections now route modeled indications through this helper, with sixteen extra
v1/v2, aligned/unaligned, tracing/release-timing and MAC-source-branch selections.
303 parser contracts cover all lengths 0..36, both formats, unaligned input,
unknown type ownership, failure/cancel and absent packet/context/buffer/data.
Twelve new mutations target length checks, IDs, MAC/WDS/count fields, delivery,
free, cancellation accounting and borrowed ownership; 56 inherited controls
keep their original modeled unmap path. These counts await accepted CI.

The generic dispatcher and HTC/HIF registration/transport are compiled and
source-reviewed, not executed by this host fixture. The BIG_ENDIAN_HOST probe
converts host-word MAC byte representation before calling that original source
branch on a little-endian host; it is not big-endian platform certification.
Initial DP objects/references/maps and peer-gone gate, platform primitives and
cleanup/event/AST/statistics endpoints remain models. Nbuf/DP heap storage is
actually freed on the host under sanitizers. No real firmware delivery,
concurrent producers, automatic parent shutdown, active SSR, phone/RF or AirDrop
validation is claimed. Backend remains disabled.
