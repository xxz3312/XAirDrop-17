# 0143：退出所有权移交与完成回执

新增桥接到现有原生 host registry 的显式移交，连接其 ordinary-idle/限定 SSR 清理路径。移交后关闭新启动、清空 bridge 的 host/HDD 借用指针，保留独立完成回执。移交返回 EINPROGRESS；只有对应 host 真正释放后，后续 poll 才可完成 bridge retire。

## 上游依据和差异

- Weverses/OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d`，`kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch`，blob `8874b020b4d7eadea41adea787d53dcca08a3c62`：复核原生 init/deinit、vdev sync 和 `g_wt_ctx` 释放。popsicle 的已有异步 runtime 不能把“接口已交给退出路径”当作同步 deinit 完成。
- Leekin2/XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb`，`module/service.sh`，blob `b4ab67069aaf3c3eac29853af993b858a4960fe2`：复核未完成会话/启动状态处理。本次保留已有手动 KSU 入口，不新增开机加载、自动恢复或强制清理。

偏离上游的部分是私有完成回执，不改变公开 Wonder ABI、CNSS2 ABI 或现有固件清理策略。它适应本项目已有的非阻塞清理、所有权 registry 和恢复范围门禁。

## 合同

- `mishare_wonder_host_handoff_receipt_locked` 沿用现有 ordinary-idle handoff 的 RTNL/独占 PSOC transition、身份、上下文和非 recovering 条件。失败保留 caller host；成功只有 registry 能清理它。
- 回执使用零初始化、不可复制的 caller-owned 值对象。它不保存 HDD/host/PSOC 指针；独立 module lease 保留代码文本。调用者仍需保护每次 API 调用直至返回，不能丢弃未消费回执。
- 所有 PSOC 共享串行分配器；序号不重复、不回绕。达到上限返回 EOVERFLOW。失败移交可以消耗序号，但不重新使用它。
- poll 在 registry 锁内查找精确序号；仍在 registry 返回 EINPROGRESS，不触发清理、不清除错误、不查询旧 HDD。确认释放后消费回执、放开独立文本引用，重复 poll 幂等。
- host registry 移除与最后元数据 `kfree` 位于同一临界区；poll 不能在元数据释放前看到“已消失”。native adapter/runtime/sync 和父级分配引用均已在此之前按原路径清理。`kfree` 不睡眠，原生销毁调用不在 registry 锁中执行。
- bridge handoff 永久关闭启动，成功后丢弃旧 HDD 指针；retire/scope 识别已移交状态，直接 poll 回执，允许原 HDD/设备上下文已经退出时完成确认。
- 一个旧回执不会因新 host 占用相同地址而等待或消费新会话。模块文本引用防止未消费回执跨越模块卸载/重新加载后遇到重置的序号空间。

## 验证和限制

本地 100 项 Python 回归、Python 语法及 diff 检查通过。[Actions 42341386219](https://github.com/xxz3312/XAirDrop-17/actions/runs/42341386219) 的 bridge-controller 作业 `128309612071` 和 stop-admission 作业 `128309612128` 已成功，既有 host/runtime/执行控制器/原生生命周期模型和新增两项回执负向控制均通过，日志未见 sanitizer 报错；完整目标编译仍在运行。C 编译仍仅在 Actions 执行：实际 host fixture 新增文本引用失败、recovering 拒绝、序号上限、ordinary idle/runtime 等待、限定 SSR 等待、释放前不可完成、父级查找失效后 poll、旧/新回执隔离和最后释放的锁可见性；两个负向控制要求提前完成和提前释放 registry 锁的变异均被行为断言拒绝。bridge/scope fixture 同时覆盖移交失败保留 owner、移交后禁用启动，以及不再进入 PSOC/HDD 查找的 poll。

这是退出所有权和完成确认的连接，不是完整的跨调用父级组件/固件租约。它不新增清理 worker、不自动触发 idle/SSR；没有清理入口调用时回执会继续 pending。原生 post-disable、MC drain、恢复来源等既有限制仍生效，已进入 START/UP 的 SSR 恢复仍不支持。不能在恢复已经开始后用 ordinary handoff 抢走 caller-owned host。

公开 Wonder init/poll/retire 尚未安装这个调用链，RX/TX 与 Apple 互通尚未验证。下一阶段需要在实际 managed owner 的 quiesce/退出点安排所有权移交，继续保留锁序和恢复阶段门禁；本轮手机无需操作，不重复 apply。
