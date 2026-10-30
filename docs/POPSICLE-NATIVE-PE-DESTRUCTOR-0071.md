# 0071：执行原生 PE 析构，补齐会话回收验证

0070 的显式 SSR 回收仍只覆盖 pre-PE INIT。0071 没有扩大这个准入范围，也没有启用无线 backend。

扩展 PE 回收前发现：既有 PE C 模型把 `pe_delete_session()` 简化成清 valid/vdev 和释放 MAC 引用，无法检查真实析构中 DPH 表、peer index pool、关联/信标/IE 缓冲区、确认定时器与父引用的顺序。现在新增独立 Actions C 模型，在原有生产 runtime、MC request/flush、身份和失败用例上，执行固定 MiCode 版本的完整 `pe_delete_session()`、`lim_clear_mbssid_info()` 和 `lim_clear_pmfcomeback_timer()`。

模型额外填充所有可选析构字段，跟踪每块分配并拒绝重复/外来 free；借用的 DPH node array 必须归零且不能 free。MAC VDEV 引用释放时检查会话已经失效、vdev/mac_ctx 清空、所有模型分配释放。覆盖匹配/不匹配/未运行确认定时器、默认认证超时的三个分支，以及重复/NULL 删除。PAS 路径若执行 AP/STA 专用定时器操作即失败。负对照去掉原生 MAC 引用释放，必须在原有 owner 回收中触发断言。

本地 53 项 Python 检查通过。新增原生 C 模型、负对照和完整编译验证待 CI。

这里的“执行原生析构”不等于真实 PE 组件和内核定时器都已执行：PE 分配、析构调用的 cleanup primitives、调度器、锁及物理父对象仍为模型。普通 live-MC 删除验证不能直接授权 MC 停止后的 SSR 删除。下一步仍需核对这些 cleanup callees 在停机窗口的约束，接入 PE/UP 回收与原生父资源协调；完整 monitor 也尚未完成。手机无需操作，没有新测试包。
