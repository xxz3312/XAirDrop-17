# 0142：桥接的原生单次调用保护

实现 `mishare_bridge_step/retire` 的内部进程上下文入口。先取得设备分配引用和原生 PSOC transition，等待已有 operation 排空，再 trylock RTNL，最后在保护范围内查询当前 HDD。锁/身份门禁失败不会执行 host 调用或改变 bridge；每次返回都释放 RTNL、transition 和本次设备引用。

这是父级协调的单次调用部分。它不在异步调用之间持有 transition，也不将 device/PSOC/PDEV 分配引用当作 HDD/组件/固件的完整寿命保证。跨调用寿命、SSR 关闭和后续恢复协调尚未完成，因此没有连接到公开 Wonder 回调，也没有新手机包。

## 上游和原生依据

- Weverses/OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d`，`kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch`，blob `8874b020b4d7eadea41adea787d53dcca08a3c62`：重新检查 init/deinit 的 RTNL、vdev sync、上下文验证、接口创建和释放顺序。
- Leekin2/XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb`，`module/action.sh`，blob `024cd17fb19c50c10f204552f8a2cd6fffc5d30a`：保持手动启动、原厂 CNSS2 和现有设备加载边界；本次不改安装/Action。
- 固定 WLAN 原始源码 `36df473046706a5259942e1bf7222108dbbb860f`：检查 `qcacld-3.0/os_if/sync/{inc/osif_psoc_sync.h,src/osif_psoc_sync.c,src/osif_vdev_sync.c}`。使用现有非等待 `osif_psoc_sync_trans_start` 与配对的 wait/stop，不创建新的同步实现。

偏离上游的原因：上游 Wonder init 已持 RTNL 并使用 vdev transition；本项目已有 host helper 要求独占 PSOC transition。新入口只允许调用者不持 RTNL/原生 operation/transition 的进程上下文，避免在反向锁序中阻塞获取 RTNL。原有已经持锁的 `_locked` API 保留。不能把该入口直接填入上游已持 RTNL 的回调。

## 返回与所有权

- device 缺失、HDD 缺失/设备不匹配、PSOC/PDEV 缺失：EINVAL/ENODEV，不触碰会话。
- transition 冲突：保留原生返回码；RTNL 冲突：EAGAIN，释放本次 transition，不重放会话步骤。
- HDD 查询发生在 transition、操作排空、RTNL 之后；不先解引用 bridge 里曾经借用的 HDD 指针。
- step 先验证当前 HDD 健康，再推进 0141 控制器。HDD 身份变化由控制器拒绝；host 内部继续检查其固定父级身份。
- retire 使用相同进入保护，但不使用全局健康检查阻断普通回收，仍由 host destroy 的自身生命周期检查决定结果。它不授权 SSR reset，也不会在 SSR 保留的 transition 之上强行进入。
- 非零返回保留原有 host 槽；锁失败不把启动记为失败，不改变 closing。正常 retire 进入控制器后才永久关闭新启动。
- 调用者必须串行化 bridge、持有 WLAN 文本和有效 device 引用。等待 operation 排空可能睡眠；调用者不得持有要被排空的 operation 或 RTNL。scope 不建立后台重试机制。

## 验证

本地 100 项 Python 回归、Python 语法与 diff 检查通过。[Actions 42327650832](https://github.com/xxz3312/XAirDrop-17/actions/runs/42327650832) 的 bridge-controller 作业 `128266568634` 已成功，三个 session/bridge/scope PASS_ONLY 标志均已核对，未见 sanitizer 报错；旧 host 夹具随后暴露声明顺序问题：模拟的 PSOC/context 函数定义位于生产 include 之后，缺少前置声明。已补齐夹具声明；修复后的 [Actions 42327840421](https://github.com/xxz3312/XAirDrop-17/actions/runs/42327840421) 三项 bridge 检查再次通过，host/退出回归作业 `128267185805` 也已通过，包含实际 host、runtime、执行控制器及原生生命周期的既有模型；完整目标编译和其余门禁作业也已通过：八项必选 success，可选 ICNSS skipped。未对这一轮完整 ELF 另行下载独立验收，不替换当前实机的已验收产物。新增 Actions-only fixture 执行实际 scope 和 bridge 头文件，模型断言取得/释放顺序、锁冲突后无会话变化、HDD 查找时机、身份变化拒绝、上下文失效后普通退出、异步退出所有权及引用平衡。真实内核的并发、等待图、父级跨调用寿命、固件和 RF 未经这个模型验证。

新头文件随 setup 复制并由真实 host.c 包含；完整编译检查实际原生 API 的类型/可见性。上一轮 0141 的完整 CI 已全部通过，但这不等于手机上的 Wonder/RX/TX 或 Apple 发现已经可用。

下一步仍是将跨调用生命周期和原生 SSR/退出路径接到同一个会话所有者，随后再连接公开 init/poll/retire 与收发配置。保持手机当前状态，不重复 apply。
