# 0160：内部会话接入固定速率准备

0159 全部八项必选 CI 已通过。本轮开始连接初始化准备主线；生产内部入口与 controller 已实现，公开 Wonder/managed init 和 START 保持关闭，手机无需操作。

## 上游与范围

修改前重新读取 Weverses/OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` 的 `kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch`，参考 init 中 fixed-rate 调用及 stop/deinit 顺序；读取 Leekin2/XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb` 的 `module/action.sh`，继续保留原厂 CNSS2 与手动部署/恢复合同。

本项目的 owned CREATE/context/PE/channel、MC rate post 与回执已有实现，但 managed prepare 仍只保存请求、禁止 raw step。此次不绕过该合同，不改变全局国家码或公开入口，而是增加内部可测试的 pre-START 准备流程。没有替换上游或新增 WLAN patch。

## 实现

`wlan_hdd_mishare_prestart.h` 的 caller-owned controller 先固定频率、两频段 NSS 和速率五个有效参数，拒绝接管已开始的普通 session 或已有外来 rate 请求。所有 poll 必须由调用方串行，并保留相同 runtime/父级/固件生命周期。

早期复用 session controller：CREATE → legacy/WMA/self-peer → PE → channel；PE/channel 接受提交不当作完成。到 PLAN 后停止调用旧 session step，等待真实 channel completion，再一次性调用已有 runtime_rate_configure。one-shot 标记先于调用，兼容 inline completion；提交返回和回执观察仍分开。

之后逐项核对 requested/posted/accepted/completed、相同请求、完整提交掩码、非 busy、无首个错误与结果错误。MC completion 在 reservation 释放前发布，因而 work_pending/work_users 尚存时继续等待。错误进入原 session sticky error，禁止重试。速率完成的零返回只表示命令提交完成，不是 firmware ACK、radio UP 或完整 Wonder init；stage 始终停在 PLAN，runtime 对 rate.requested 的 START 拒绝不改。

新增 `mishare_wonder_host_prestart_step_locked`，沿用 RTNL、原始 parent identity、context 与接口 DOWN 检查，连接实际 host.session/runtime。旧 raw host session 入口在 prestart.selected 后返回 EBUSY，防止从另一入口跳过配置流程。退出复用现有 session.closing/host cleanup 和 0151–0159 清理合同。

## 验证

100 项本地 Python 回归、语法/diff 检查通过。本地没有编译 native/host 组合。

新增 Actions-only controller 夹具实际包含生产 prestart/session headers，native 创建/PE/channel、rate post/receipt 由模型提供：16 组 inline/异步、NSS、HT/HE、工作引用等待组合；15 类回执/状态错误；post 失败不重试、不支持参数、外来 session/rate 拒绝；五项变异控制针对模式选择、post 标记、channel wait、work drain 和提交掩码。原 session controller 回归同时执行。host 原生夹具增加旧入口拒绝及新入口 snapshot 错误保留检查。新 header 纳入目标源复制，实际 host API 会在完整 WLAN 编译中验证。上述 Actions 尚待执行。

## 剩余边界

尚未连接 managed immutable init 请求与该内部 controller，没有完整跨调用 parent lease/全局配置事务，也没有配置后 START/UP/RX/TX。当前 API 仅支持既有 HT20/受限 fixed-rate 合同；国家码/完整监管许可仍需调用方在 native scope 中验证。模型回归不等同于原生全链运行，更不等同于手机、空口或 Apple 互通。
