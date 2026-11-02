# 0098 Native DP peer unmap and map-reference release

离线验收完成：[CI 41497778660](https://github.com/xxz3312/XAirDrop-17/actions/runs/41497778660)（`80f9194`）两项作业成功。相关实现、边界用例、失败控制和 CI 入口集中完成后统一编译验证。

This stage extends 0097 with four original functions: `dp_rx_peer_unmap_handler`,
`dp_peer_get_ref`, `__dp_peer_get_ref_by_id` and
`dp_peer_find_id_to_obj_remove`. The two original DP peer/VDEV finalizers remain
unchanged. Initial lifecycle and map CONFIG references are distinct; the native
lookup takes a temporary HTT reference using nonzero-ref admission. Native map
removal clears peer/txrx IDs and the map slot and returns its CONFIG reference
while holding the modeled map lock. Native unmap performs its remaining steps,
returns HTT and lifecycle CONFIG, and reaches native peer/VDEV final free when
all additional references are gone.

The 120 previous combinations now use native unmap. Thirty-two extra cases
combine offload, IPA, optional txrx/WDI notification, optional OL/partner hooks,
reference tracing and extra-reference release before/after unmap. Probes cover
unknown/boundary IDs, zero-ref lookup, WDS offload skip, both WDS AST results,
and duplicate delivery after peer storage is gone. WDS paths must return the
temporary HTT reference while retaining CONFIG references and the mapping.
Ten new mutations target lookup pinning, map slot/reference/txrx-ID removal,
Qref and flow cleanup, event/state order and the final HTT/CONFIG releases.
The 46 inherited controls run with their previous modeled unmap setup, preserving
the meaning of those tests. All checks passed in the accepted run.

This executes native handler C from fixture calls, not real firmware delivery.
Initial construction, map/lifecycle reference acquisition, the map array,
platform atomics/locks, event/Qref/AST/flow/IPA/WDI/OL/partner/statistics endpoints,
peer-gone admission and release scheduling remain models. Peer create/map-add/
delete, firmware HTT parsing/transport and callback registration do not execute.
WDS AST helpers are modeled; STA and multiple-SOC/MLO ownership paths are not
selected. DP and ObjMgr peer objects remain distinct with no verified production
bridge. Inherited component/coordinator/concurrency boundaries remain. Host heap
free is not kernel allocator execution. No backend activation, active SSR,
phone/RF validation or AirDrop certification is included.

## 验证记录

首次统一运行在夹具 attach 的两条同行 if 触发 `-Werror=misleading-indentation`，修正花括号后重跑成功；六个原生函数体未改写。失败记录保留在验收 JSON。最新组合前置执行，旧组合和完整构建保持执行。

152 组组合、56 项失败控制（46 项继承、10 项新增），0097/0096/0095/0094/0093/0092 六项独立组合、53 项 Python 检查、旧回归、完整 WLAN 编译、CNSS、严格链接、七项选定布局和模块记录检查均通过。继承的 46 项控制在其原有模型 unmap 入口运行；新增正常组合及十项控制执行本轮原生入口。

本轮及六项旧组合生成源码的独立重建哈希均与 CI 相同；本轮 SHA-256 为 `176de0cc5b7bfd3c9e26d7dfb121a808fbe7c2914b4498ba3b677ee4ac4e7a67`。六个 DP 原生函数体、三个来源文件的原始 Git blob、enum/HTT 常量来源、50 份报告中的生产源码、37 个路径别名、固定源码清单及两份 ZIP digest 均已核对。布局候选对应最终链接 WLAN；五个模块无版本记录不匹配或缺版本依赖，WLAN 无未解决依赖。本地未执行 C 编译。见[完整验收 JSON](research/popsicle-native-dp-unmap-0098-validation.json)。

本轮执行的是原生 unmap 处理函数及引用/map/最终释放函数，事件仍由夹具调用；固件 HTT 消息解析、事件注册/输送、真实清理组件、生产停机协调和整机验证仍待继续。backend 保持关闭，手机无需操作。
