# 0071：隔离 PAS 的共享认证定时器清理，执行原生 PE 析构

发现并修复私有 PAS 会话的 PE 删除会走普通 SAE cleanup 的问题：原生 `lim_sae_auth_cleanup_retry()` 无条件调用 `lim_deactivate_and_change_timer(..., eLIM_AUTH_RETRY_TIMER)`，可能干扰其他会话使用的共享认证重试定时器。0033 补丁让 `eSIR_MISHARE_PAS_MODE` 跳过该调用；其他 BSS 类型保留原生行为。源码审计严格还原这一个有界替换后，继续核对整个普通会话源码基线。

0070 的显式 SSR 回收仍只覆盖 pre-PE INIT。0071 没有扩大这个准入范围，也没有启用无线 backend。

扩展 PE 回收前发现：既有 PE C 模型把 `pe_delete_session()` 简化成清 valid/vdev 和释放 MAC 引用，无法检查真实析构中 DPH 表、peer index pool、关联/信标/IE 缓冲区、确认定时器与父引用的顺序。现在新增独立 Actions C 模型，在原有生产 runtime、MC request/flush、身份和失败用例上，执行固定 MiCode 版本的完整 `pe_delete_session()`、`lim_clear_mbssid_info()`、`lim_clear_pmfcomeback_timer()`、beacon filter、power cleanup dispatch 和实际 SAE cleanup。

模型额外填充析构函数中直接处理的可选字段，跟踪每块分配并拒绝重复/外来 free；借用的 DPH node array 必须归零且不能 free。MAC VDEV 引用释放时检查会话已经失效、vdev/mac_ctx 清空、所有模型分配释放。覆盖匹配/不匹配/未运行确认定时器、默认认证超时的三个分支，以及重复/NULL 删除。PAS 路径若执行 AP/STA 专用定时器操作即失败；原生分派还必须保留其他 STA/SAP 的 beacon filter，并且不查询/修改并发会话功率状态。两个负对照分别去掉原生 MAC 引用释放，以及移除 PAS 的 SAE 隔离；前者必须触发引用释放断言，后者必须执行实际 SAE helper 并触发共享认证定时器断言。

[CI 41123670326](https://github.com/xxz3312/XAirDrop-17/actions/runs/41123670326)成功：53 项 Python 检查、新增原生 PE 析构模型与两个负对照、既有 C 模型、完整 WLAN/Wonder/provider 编译、严格模块链接和七项布局检查通过。下载报告的 ZIP SHA256 与 GitHub digest 一致；生产 runtime/header、三个 native 文件和六段函数哈希已独立核对，8 个提交文件与本地 blob 一致。见[验证记录](research/popsicle-native-pe-destructor-0071-validation.json)。

共享定时器的源码顺序也已核对：`lim_deactivate_and_change_timer` 的 AUTH_RETRY 分支先停用全局 `g_lim_periodic_auth_retry_timer`，之后才按该定时器保存的 sessionId 查找会话并修改周期；没有检查本次删除的 PAS owner。这是源码调用顺序审计，实际内核定时器仍未在手机上执行。

这里的“执行原生析构”不等于真实 PE 组件和内核定时器都已执行：PE 分配、其余 cleanup primitives、实际定时器操作、调度器、锁及物理父对象仍为模型。普通 live-MC 删除验证不能直接授权 MC 停止后的 SSR 删除。下一步仍需核对这些 cleanup callees 在停机窗口的约束，接入 PE/UP 回收与原生父资源协调；完整 monitor 也尚未完成。手机无需操作，没有新测试包。
