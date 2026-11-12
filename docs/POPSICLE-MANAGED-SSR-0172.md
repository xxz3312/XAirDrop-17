# 0172 typed managed owner 接入原生 SSR 协调

## 基线和上游参考

0171 修正版 `8e440fa4218db1a997637b14498366d3f44c441a` 的 Actions [43173756828](https://github.com/xxz3312/XAirDrop-17/actions/runs/43173756828) 八项必需任务全部 success，包括完整 WLAN 目标构建/严格链接。可选 ICNSS 跳过，不是目标 CNSS2 缺项。

本批重新核对 Weverses/OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` 的 `kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch`，以及 Leekin2/XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb` 的 `module/action.sh`。上游全局上下文卸载/恢复不具备本项目异步 request/instance 账本；复用本项目已验证的原生 post-disable 调用位置、PSOC transition、RTNL trylock 和 runtime qualified SSR reclaim，不复制全局指针或绕过原生回收资格。

## 自动协调的范围

在现有 `mishare_wonder_host_ssr_prepare_locked` 的恢复检查之后，处理相关且带父级登记的 typed managed 实例，再检查剩余 host/runtime。未绑定父级的纯 metadata/prepare 实例不需要原生回收。raw caller-owned host 仍拒绝自动接管。

注册表锁下预检相关实例的 HDD/device/PSOC/PDEV 和 busy 状态，成功后 claim 一个实例；不在锁下调用原生函数。父级 exclusive transition 和操作排空仍由原生 SSR 调用者持有。只尝试获取 RTNL，不等待反向锁；争用释放 claim 并返回 EAGAIN。无实例快路径不额外获取 RTNL。

持有 claim 后核对 canonical request、typed 模式、attempted 和单一 owner/receipt 形状；随后永久关闭 bridge 的新调用入口。直接 owner 使用同一个 `bridge.host` 权威槽调用现有 SSR reclaim；已交接 owner 使用原注册表回收和原退休凭据，绝不重建 host 指针。runtime 批处理仍要求完整的同 PSOC owner 覆盖和原生 SSR/MC/transport 资格；本批没有放宽这些规则，不新增固件命令或 reset/ACK 证据。

只有实际 host/receipt 回收完成且 receipt/module lease 已消费后，才清除 instance 的 HDD/PSOC/PDEV 登记。bridge 已 retired/closing，不再保留 borrowed HDD；instance metadata、模块引用和 device 引用仍由原调用者持有。后续 process-retire 可以在 HDD 查找已不存在时完成 metadata 释放。父级 stop 最后仍检查所有剩余 host/runtime；全局卸载仍受 metadata 实例及其模块引用保护。

忙、身份/请求错误、原生异步等待及硬错误不释放父级登记或替换 owner。部分进展不是成功。多个 runtime 的完整覆盖仍由现有 batch preflight 限制，无法完整覆盖时保守保留，不宣称新增一般多会话 SSR 支持。

## 验证与限制

完整 host fixture 执行实际生产 instance/coordinator/reclaim/receipt 代码，新增四种成功状态（host-only、runtime-attached、handed-off、failed create）和九种保留边界（busy、RTNL 争用、PDEV 替换、非恢复状态、native wait、native hard error、额外 owner、请求修改、retire-broken）。错误子进程有意保留资源退出，不伪造生产重置或故障恢复。成功测试核对实际 host/runtime 模型释放、无重复回收、关闭后的请求拒绝、撤下登记后的 stop admission，以及无 HDD 的 metadata 释放。

九项行为变异检查覆盖原生接线、busy claim、请求一致性、closing、提前/遗漏撤销父级登记、原生 wait 结果、busy 释放和 RTNL 释放。修正原 parent-fence 报告中与后续 parent mutation 变量同名而导致计数不准确的问题。

本地 100 项 Python 回归、py_compile、diff 检查和九项变异构造检查通过。生产 host sanitizer 与完整目标构建交给同一轮 CI，提交时尚未观察结果。此 fixture 的 runtime batch、native transport/固件资格、锁和完成源仍有平台模型；真实 runtime 和 native lifecycle 的既有组合回归继续运行。自动调用位置沿用已有真实 native post-disable 接线，但没有本批实机 SSR 或射频验证。

保留原厂 CNSS2，不触碰 init_boot，不开放公开 Wonder init/START。Apple 发现、握手与双向文件传输仍未认证；手机无需操作。

忙实例返回 EINPROGRESS 以适配原生 stop journal 的 POST_DISABLED pause/resume；EBUSY 会被该 journal 记录为硬错误。新增实际 journal begin/step/pause/resume 组合及一项 errno 变异来验证该区别。首次 CI 的未变异 host 基线通过；故障变异先命中了旧的最终释放断言，已将 busy/closing/父级清空的检查前移至 SSR 成功出口，修正版仍以新 CI 为准。
