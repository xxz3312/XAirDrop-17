# 0069：SSR runtime 到 host 最终释放的入口

`mishare_wonder_host_reclaim_ssr_locked` 将已有显式 SSR runtime batch 回收接到 host 生命周期。旧的普通 destroy 继续拒绝隔离中的 runtime；新入口只在 recovering 状态、原 psoc 身份保持、网卡未打开时交出 runtime 句柄。host session 永久关闭准入，句柄暂时转交 batch 并在所有返回路径恢复最新值。

单个 runtime 必须覆盖该 psoc 的完整 registry；如果还存在其他 runtime，batch 在任何 native 回收操作前返回 EBUSY。即使 host 已经没有 runtime，也执行空表的完整覆盖检查。batch 继续要求原始 SSR fence、owned MC 排空、合法恢复策略以及实际 final-free。它支持已有 pure host、早期未 prepare NDI、普通清理已完成的最终回收；prepared/UP 回收并未新增。

只有 batch 返回 0 且 host runtime 为空，才调用普通 host destroy 完成 sync 注销、operations 排空、adapter 关闭和 sync 销毁。runtime 已释放但 sync registry 错配时，保留 host，修复登记错配后由显式轮询重试最终关闭。host 从 registry 移除前，0068 的 idle inhibition 一直保持。

该入口仍要求调用方持有 RTNL、独占 psoc transition，并在所有异步轮询期间保留精确的 HDD/psoc/pdev/DP/timer/netdev 父资源。它没有安装原生 shutdown 调用方，未形成 SSR/remove coordinator 或父资源租约，不能阻止物理 remove。recovering flag 本身不证明 IRQ/MC/DP 已排空。HDD backend init 仍不分配无线会话，不发手机测试包。

扩展 Actions host C 模型验证非 SSR、psoc 变化、打开/运行中网卡、coverage 拒绝、连续 EINPROGRESS、policy 拒绝保留、runtime 已释放但 sync 关闭失败、无 runtime 的 host 仍需完整 registry 检查，以及闲置关机保护持续生效。此处 batch 是返回值/句柄模型；真正的 runtime batch、原生 callback/final-free 与恢复策略仍由既有独立 C 模型验证。[CI 41110041682](https://github.com/xxz3312/XAirDrop-17/actions/runs/41110041682)成功：53 项 Python 检查、host C 模型和既有生产 runtime batch 与原生函数片段模型、完整 WLAN/Wonder/provider 编译、严格链接及 7 项选定布局检查通过。新入口已在实际 WLAN 模块定义符号中核对；host 模型生产文件哈希、重建的完整 C 输入哈希及 runtime batch 生产源码哈希与产物一致。下载 ZIP 的 SHA256 与 GitHub digest 一致。见[验证记录](research/popsicle-host-ssr-retire-0069-validation.json)。

目标原生 `hdd_wlan_exit` 的顺序是 stop/deinit all adapters → `hdd_wlan_stop_modules` → close all adapters；`hdd_close_all_adapters` 会直接注销 sync、关闭 netdev，没有专用 owner 判定。已登记的 PAS host 必须在这些通用路径中由专用生命周期协调，不能等 modules/DP/pdev 关闭之后再调用此入口。早期 NDI 的合格恢复窗口位于 native `cds_post_disable` 完成 HIF/HTC/RX/WMI/MC 停止之后、DP/pdev close 之前。下一步原生协调器需同时处理这些顺序约束与 prepared/UP 清理；本轮没有改写这些通用路径。
