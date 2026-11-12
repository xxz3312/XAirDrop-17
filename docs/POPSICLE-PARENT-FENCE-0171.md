# 0171 跨轮询父级退休登记（第一批）

## 参考与边界

核对 Weverses/OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` 的 `kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch`，以及 Leekin2/XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb` 的 `module/action.sh`。上游分别使用全局 Wonder 上下文同步清理和驱动替换/恢复脚本；没有本项目异步 managed request 的注册表合同。本批继续沿用原生 PSOC transition/RTNL 和现有 stop journal 门禁，不跨回调持有原生 transition，不增加公开初始化、部署或 init_boot 操作，保留原厂 CNSS2。

## 实现

- typed managed 首次实际尝试 request bridge 后，在释放单轮 native scope 前发布 HDD/PSOC/PDEV 身份。单纯 prepare、scope/策略拒绝不会登记。登记和 stop 观察共用 host registry 锁。
- 登记属于 instance，独立于 host/runtime 指针。host 创建失败但 attempted 已冻结的实例，以及 host 已交接而 instance 尚未退休的实例，仍阻止父级 stop 就绪。
- PSOC busy、同 HDD 父级迁移检查和全局卸载门禁纳入 instance；卸载对所有已注册实例保守拒绝，包括 metadata-only 实例。已有 module/device 引用保持不变。
- typed 下一轮和有原生资源的 process-retire 先重新获取 scope，再比较保存的身份；不在进入 scope 前解引用旧 HDD。身份变化不覆盖旧登记、不提交清理、不释放 owner。
- 只有实际 host/receipt 退休确认后才从注册表移除 instance。没有原生 owner 的失败创建走 metadata 退休；不需要为了空 owner 提交固件清理。scope 失败、异步等待、SSR 拒绝或身份异常均保留登记。

这是一项接入现有原生停机门禁的父级退休保护，不是防止 SSR 固件失效的长期固件 lease。仍要求调用者保留并协调原生生命周期；未审核的外部拆除路径不由此认证。SSR 会关闭/停止原生运行状态，尚未实现从仍由 managed caller 持有的 host 自动移交到 qualified SSR 回收。现有已交接 host 的 SSR 仍可回收，instance 登记在 receipt 被消费前继续阻止最终 stop 就绪，后续重试才能通过。普通退出和部分初始化失败继续使用同一个 authoritative owner。

## 验证合同

完整 host fixture 执行生产 instance、父级登记、原 stop-ready/unload 和退休代码，增加跨轮询登记/父级替换/SSR 退出拒绝，以及无 host 的首次分配失败后 idle/SSR/unload 拒绝与最终释放。五项行为变异分别移除发布、PSOC 观察、迁移观察、调用前身份检查和卸载 instance 观察；必须编译成功并在指定行为断言处失败。request bridge fixture 增加 scope 内父级边界调用模型；父级注册表本体由完整 host fixture 验证。

100 项本地 Python 回归、py_compile、diff 检查通过。原生 sanitizer 执行与完整目标 WLAN 编译集中交给本批 Actions；提交时结果待观察，不能写成已通过。模型不证明固件 ACK、实机 RF、公开 init/START 或 Apple 发现/握手/双向传输。手机无需操作。

## 2026-11-12 验证修复

0170 修正版 `c47500861fcf9b1a1fdb48f3851506ebc19f8406` 的 Actions `43082708943` 全部八项必需任务 success，包括目标构建。

0171 `3d9fdcc9b4f8f4ce8984139fb8778ce82449ebcd` 的 Actions `43084226811` 中，stop-admission 与 diagnostic 均被同一个 host fixture 的 `mishare_runtime_psoc_busy: parent_owned` 断言阻断。诊断任务尚未进入完整目标构建，不能称作生产驱动编译失败。新增的停机观察在 managed API 退出 scope 后直接调用 locked helper；现改为通过实际 `mishare_bridge_scope_begin/end` 观察忙、迁移及最终空注册表，检查入口/退出均未持锁。保留所有生产断言及失败保留门禁。

完整 host sanitizer 测试提前至 stop-admission 的源码准备之后，只移动原调用，不增加一次重复执行。该批修改不扩展公开初始化或 SSR 所有权移交；100 项本地 Python 回归、py_compile 和 diff 检查通过，修正版原生/目标 CI 仍待观察。

0171 修正版 `8e440fa` 的 Actions `43173756828` 八项必需任务已全部通过。后续 typed managed 的原生 SSR 自动协调见 [0172](POPSICLE-MANAGED-SSR-0172.md)；该扩展以自身 CI 结果为准。
