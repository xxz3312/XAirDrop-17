# 0068：专用 DOWN host 的原生空闲关机保护

## 修复的问题

上游 PAS host 保持 Linux DOWN，NDI 固件会话与 Linux 接口打开状态分离。目标原生 `__hdd_psoc_idle_shutdown` 只用 `hdd_is_any_interface_open` 决定是否进入 `hdd_wlan_stop_modules`。因此，仅依据网卡 DOWN 不能判断专用 host 或其异步回收已经释放。

0068 在该原生函数取得独占 psoc transition、等待普通 operations 排空后，增加精确 psoc 的 host 生命周期检查。存在 host 时返回原生已有的 `-EAGAIN`，照常释放 transition 并发送结束事件；不进入 module stop。没有该 psoc 的 host 时保留原有接口检查、module stop 返回值和事件顺序。

## 生命周期范围

`wlan_hdd_mishare_host.c` 的私有 registry 在 host 分配后、sync/adapter 创建前登记；创建失败回滚登记；成功后保持到 runtime 确认释放、sync 注销/排空、adapter 关闭和 sync 销毁之后。`EINPROGRESS`、运行中拒绝和 sync registry 错配均保留登记。spinlock 仅保护列表，不跨越 native 操作。创建与释放仍要求 RTNL 和相同的独占 psoc transition；原生 idle 决策在自己的 transition 内执行，因此查询后不能并发创建新 host。

登记只观察生命周期，不取得 psoc/pdev/device 引用；它不是 SSR/remove 的父资源租约。模式切换强制 stop、SSR、物理 remove 和其他 module stop 入口尚未由此保护。不能通过给 device 加引用或忽略 void remove 返回值声称解决这些路径。

## 验证范围

扩展既有 Actions C 模型，执行完整生产 host helper 与完整原生 `__hdd_psoc_idle_shutdown`。测试无 owner、不同 psoc、纯 host、异步 runtime drain、sync 错配、创建失败回滚、transition 失败、普通接口打开和 module stop 原样返回错误；在 sync 创建、adapter 关闭、sync 销毁的模型调用点检查登记仍存在。QDF/native synchronization、module stop 和网卡操作仍为模型；完整原生 idle 函数新增段可精确移除并恢复原函数 SHA256，较早源审计保持原基线。

本地 53 项 Python 检查、无 fuzz 补丁应用、原生 idle 完整源码精确还原、既有 parent 源审计还原以及调用顺序检查通过。GitHub 上 11 个改动文件与本地 blob 一致。[CI 41101029685](https://github.com/xxz3312/XAirDrop-17/actions/runs/41101029685)已触发，记录时仍在等待运行器，尚未执行 C 模型或完整编译；严格链接和选定布局检查亦未完成。见[验证状态](research/popsicle-idle-host-0068-validation.json)。HDD backend init 仍返回 `EOPNOTSUPP`，无手机执行、无固件启动或 AWDL 认证。本轮不发手机测试包。
