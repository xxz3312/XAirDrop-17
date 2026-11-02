# 0097 Native DP peer free and VDEV CHILD release

离线验收完成：[CI 41488890858](https://github.com/xxz3312/XAirDrop-17/actions/runs/41488890858)（`c4926c2`）两项作业成功。相关实现、边界用例、失败控制和 CI 入口集中完成后统一编译验证。

This stage extends 0096 with the pinned, byte-identical `dp_peer_unref_delete()`
body. A separate host heap DP peer represents the owner of the DP VDEV CHILD
reference. Modeled admission clears its peer-ID mapping, then selected callers
release CONFIG/HTT/TX and optional RX references through the original function.
Nonfinal releases must preserve both objects. Native finalization requires an
invalid peer ID and empty AST, removes optional inactive-list membership, calls
cleanup endpoints in original order, frees actual host peer storage, and returns
the CHILD reference into native `dp_vdev_unref_delete()`. That function frees
host VDEV storage before the existing production runtime callback is invoked
through the 0096 checking trampoline.

All 104 previous composite sequences use native peer finalization. Sixteen new
combinations cover reference tracing, RX's original per-module-counter bypass,
reversed CONFIG/HTT release order, inactive-list absence, extra peer TX refs,
extra VDEV HTT refs and optional VDEV notification. Ten added peer mutations
cover final-ref admission, mapped-ID guard, inactive unlink, AST guard, state,
cleanup, lock/txrx order, peer free and CHILD put. Two additional rejection cases
exercise unmodified native mapped-ID and AST admission, alongside 34 inherited
controls. All checks passed in the accepted run.

DP peer and object-manager peer are separate objects. The firmware unmap handler
and real peer allocation/delete/map APIs do not execute. Construction, reference
acquisition, ID-map invalidation, peer-gone gate and release scheduling remain
fixture models; this does not establish a production DP-to-ObjMgr bridge. AST
starts empty; SAWF/state/peer cleanup/monitor/txrx/minidump endpoints and platform
locks/lists/atomics are models. Sanitizers observe actual host heap free, not a
kernel allocator. Inherited components and shutdown coordinator remain modeled
or absent. No production kernel change, radio activation, phone test, firmware,
real concurrency, active SSR or AirDrop certification is included.

## 验证记录

120 组组合、46 项失败控制（34 项继承、10 项新增变异及 2 项未改写原生 admission 拒绝）、0096/0095/0094/0093/0092 五项独立组合、53 项 Python 检查、旧回归、完整 WLAN 编译、CNSS、严格链接、七项选定布局和模块记录检查通过。

本轮及五项旧组合源码独立重建哈希均匹配 CI，本轮 SHA-256 为 `aebeabfba4b6e91eeda8128ee1ad858da472868dbc2dbf8e7968d0bd49c9a9f2`。两份 DP 原生函数体、原始文件 Git blob、enum/HTT 常量来源、49 份报告中的生产源码、37 个路径别名、固定源码清单及两份 ZIP digest 均核对。布局候选对应最终链接 WLAN；五个模块无版本记录不匹配或缺版本依赖，WLAN 无未解决依赖。本地未执行 C 编译。见[完整验收 JSON](research/popsicle-native-dp-peer-free-0097-validation.json)。

本轮新增的是原生 DP peer 最终函数体到 VDEV CHILD 归还的验证，固件 unmap handler 尚未接入，真实组件、生产停机协调及整机验证仍待继续。backend 保持关闭，手机无需操作。
