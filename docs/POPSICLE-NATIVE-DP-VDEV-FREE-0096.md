# 0096 Native DP VDEV final free and runtime completion

This stage extends 0095's composite with the pinned, unmodified
`dp_vdev_unref_delete()` body from `dp_main.c`. It does not change the
production kernel backend or enable radio capabilities.

The selected passthru cases allocate host heap DP VDEV storage. Modeled detach
registers the callback/token supplied by the existing production native bridge,
marks delete pending, publishes the optional inactive-list entry and releases
CONFIG through the original finalizer. The modeled peer-gone gate then allows
held HTT references and the final CHILD reference to be released. Native code
performs its ref checks, cleanup calls, inactive unlink, optional pre-free
notification, storage free and post-free completion. A checking trampoline
forwards the original callback token into the existing runtime callback only
after actual host heap release.

All 88 previous composite combinations use this path; 16 additional combinations
cover reference tracing, extra HTT references, optional notification and an
absent inactive-list entry. Eight new mutations target nonfinal release, cleanup,
unlink, notification, free, completion and callback-token handling, alongside
26 inherited controls. All checks passed in the accepted run.

DP construction, detach registration, initial reference ownership, late HTT
release, peer-gone admission, cleanup endpoints, optional notification, locks,
atomics and list representations remain models. No real DP peer unmap or
`dp_peer_unref_delete()` runs, and no direct DP-to-ObjMgr reference bridge is
asserted. Only passthru is selected. Inherited parent construction/components,
real kernel concurrency, automatic shutdown coordination, firmware and phone
validation remain outside this stage. Host heap free is not kernel allocator
execution. No AirDrop interoperability is certified.

验证已完成：[CI 41441718233](https://github.com/xxz3312/XAirDrop-17/actions/runs/41441718233)（`07f0c79`）两项作业成功。先集中写齐相关代码、边界处理、反向检查和 CI 入口，再统一编译验证：104 组组合、34 项负对照、0095/0094/0093/0092 四项独立组合、53 项 Python 回归、旧验证、完整 WLAN 编译、CNSS、严格链接、七项布局和模块记录检查均通过。

第一次统一验证在最后一个错误令牌负对照的生成代码中触发 `-Werror=misleading-indentation`；补上测试变体的花括号后重跑全部验证成功。正常组合生成源码和原生函数体没有因此改变，失败记录保留在[验收 JSON](research/popsicle-native-dp-vdev-free-0096-validation.json)。

独立重建的本轮及四项旧组合源码哈希均与 CI 相同，本轮 SHA-256 为 `1034802366343a6f766ca5196a9ba318cd4f3a7a6404aeab4d84a1d74b77c8eb`。DP 原生函数体、原始文件 Git blob、两份 enum 来源、48 份报告中的生产源码、37 个路径别名、固定源码清单和两份 ZIP digest 已核对。七项选定布局候选对应最终链接 WLAN；五个模块无版本记录不匹配或缺版本依赖，WLAN 无未解决依赖。本地未执行 C 编译。

本阶段验证原生 DP VDEV 最终函数体及其实际 host heap free 到生产运行时回调的衔接。真实 DP peer unmap/ref-delete、完整组件清理、并发迟到生产者、生产停机协调和整机验证仍待实现。backend 保持关闭，手机无需操作。
