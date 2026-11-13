# 0186 snapshot 的 live registry 与错误输出合同

0185 `97715bc1cf190f20ec8ee164fc67f5bd07e25d61` / Actions 43379073833 八项必需 CI 全部通过，optional ICNSS 跳过。

本批核对 OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` 的 kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch，和 XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb` 的 module/action.sh。延续原生生命周期/原厂 CNSS2；没有发现能替代本项目 opaque owner registry 读合同的对应实现。

## 修复

原 runtime_snapshot 在 registry lock 下直接解引用传入 owner，随后解锁再读 owner->radio；radio_snapshot 同样直接解引用传入 radio。Unknown/已退役句柄可能触发无效读取，radio 读取失败时 runtime 输出也已被部分覆盖。

现在 runtime 在锁下先以地址比较查找 live owner，不匹配返回 ENOENT，绝不解引用未知输入。无 radio 时在同一锁内复制 scalar 状态。有 radio 时捕获句柄，解锁执行实际 radio snapshot，成功后重新认证 live owner 和相同组件关系，再发布输出。组件漂移返回 EUCLEAN，owner 消失返回 ENOENT，底层错误原样传播；所有错误均不改变输出。Radio 在自己的 registry lock 内先查找句柄，匹配后才复制。

锁不嵌套，局部只缓存较小的 radio status，不额外复制整个 runtime status 到内核栈。radio_phase、down_send 与 radio_execute 的内部读取现在检查返回值，避免错误后使用未初始化观察值。

## 验证

在实际 factory→native runtime→raw radio 普通退出组合中运行两个生产 reader。256 正常组合检查已真实释放的 runtime/radio token 返回 ENOENT 且输出不变；保留十四类 constructor 失败和原普通退出故障。

一个 live DOWN 场景还验证 NULL/unknown 输入、成功 native 状态、坏组件句柄、scalar-only 读取及三类同步模型 cut：radio 观察后组件关联变更、owner 从 registry 摘除、底层返回错误。Cut 期间实际 storage 与父级仍保留，不执行 native cleanup，测试之后仅恢复人为读取切点；这不是生产 reset/reopen API，也不宣称任意并行 teardown 安全。

五项行为变异覆盖 unknown-owner false success、unknown-radio false success、遗漏组件身份复核、遗漏第二次 owner registry 认证、底层失败前提前覆盖调用方输出。变异须命中对应合同断言。原有 raw ordinary/SSR、factory、host 回归保持。

## 边界

Snapshot 不增加引用、不授权 START/window/cleanup。调用方仍须在整个读取期间保留并串行 native parents；不提供 allocator 地址复用/ABA 或任意并发 teardown 证明。物理 adapter/sync/ref/FW/DP 原语仍有模型。configured START/public init 和 UP/WAIT/失败 SSR 未开放。

本地 105 项 Python、py_compile、C 源构造和 diff 检查通过；原生/sanitizer 与目标构建交由 Actions，提交时待观察。保留原厂 CNSS2，不触碰 init_boot，手机无需操作。
