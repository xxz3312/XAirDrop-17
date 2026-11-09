# 0162：先取消 radio，再等待 MC 工作排空

## 已确认的问题

0161 的 prestart 独立组合通过，随后完整 Actions 42618977716 的 diagnostic 作业 129165900893 在 `Compile diagnostic objects` 中运行原有 `mishare_radio_fixture.py` 时失败：排队 START 尚未取消。完整目标构建因此不能记为通过。

普通 ndi_drain 的新 work gate 在 radio_drain 前面。排队 START 自身持有 work reservation，因此第一次 destroy 直接等待，没有向 radio 设置 closing；worker 随后运行时可能正常提交 START。原测试要求退出先取消尚未开始的 START，这个要求不能通过修改期望绕过。

## 参考与修复

修改前重新核对 Weverses/OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` 的 `kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch`，以及 Leekin2/XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb` 的 `module/action.sh`。继续复用原生 stop/deinit 顺序、原厂 CNSS2 和手动部署/恢复合同。

生产修改只调整 ndi_drain 顺序：

1. 检查速率退出资格和已有错误。
2. 执行现有 radio_drain，让 queued START 得到 closing/cancel，或让已启动 radio 走原 STOP/DOWN 流程。
3. radio 实际排空后，在 registry 锁内重新检查 blocked，再等待所有 work_pending/work_users。
4. 引用归还后才允许原有 PE/peer/VDEV/DP 清理。

零尝试 rate 完成发布时没有可启动 radio，仍会在第三步等待其工作引用；不删除 PE，不放弃 0161 的保留保障。没有清除错误、伪造回执或开放任何启动入口。

## 回归与变异

原 radio 生命周期夹具增加明确断言：queued START 有一个 pending work 时，destroy 必须设置 radio.closing，且不提交 PE/peer/VDEV/DP 删除；随后 worker 普通执行或 flush 都必须进入 CANCELLED，START/STOP/DOWN 命令计数均为零，最后正常释放。

同一 radio 夹具新增行为变异：把 work gate 从 PE 前移回 radio_drain 之前，同时保持 registry 锁配对正确；该变异必须因取消顺序断言失败，不能通过编译失败充当测试证据。既有完整 native TX/RX/PM/失败/超时测试全部保留。

将 radio 验收作为 stop-admission 的独立早期步骤，减少等到完整 diagnostic 后才发现问题的反馈延迟。0161 的生产 prestart/runtime/rate owned MC/native cleanup 512 组组合、12 组异常和四项变异保持原要求，只更新新门禁位置的变异锚点。

## 当前结果与范围

本地 100 项 Python 回归、语法/diff 和两种组合源码生成通过；大 native fixture 本地未编译。radio 及 prestart 原生执行、ASan/UBSan 和变异已通过独立步骤；完整 WLAN 编译仍在运行。

本轮优先修复已发现的完整生命周期回归，尚未继续接入 managed 请求绑定。公开 init/START 关闭；无新手机包或操作。物理 transport、固件、scheduler/ref/锁/DP 等仍有模型边界，不代表手机/RF/Apple 互通。

## 已验证结果

源码提交 `862bab76f51549ea11642e35328320c222ac7c91`，Actions 42621983916、stop-admission 作业 129176182962 的以下步骤均 success：

- Native radio cancel before work-drain ordering with sanitizers：包含完整原有 radio 生命周期、queued START closing/cancel 明确断言，以及门禁前移的行为变异。
- Native prestart configuration and ordinary retirement with sanitizers：原 512 组组合、12 组异常及四项变异完整复验，零尝试 flush 完成发布处仍禁止提前删除 PE。

bridge-controller 已 success。完整 stop-admission、其余生命周期组合及目标构建仍在运行，不记作全门禁通过。0161 的历史失败保留，并以本轮源码的独立复验证据标记已修复；没有重写旧测试期望或清除错误来绕过。
