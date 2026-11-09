# 0164：owned VDEV 的 host-MLME BSSID 一次性绑定

## 上游和差异

修改前重新核对 Weverses/OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` 的 `kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch`：init 调用 `wlan_vdev_mgr_set_param_bssid` 后才创建 PE。进一步读取同提交的 `kernel/patches/0007-session-dp-and-hardware-guards.patch`，确认 setter 是上游新增接口，所做操作为精确 MLME 组件的 `mgmt.generic.bssid` 六字节写入，无 WMI 命令。

锁定 MiCode WLAN `36df473046706a5259942e1bf7222108dbbb860f` 的 native API 只有 getter，setter 不存在。因此不调用不存在的函数，也不引入整个含 DP/硬件调整的上游 patch；在本项目 private runtime 实现相同字段/字节操作，增加 owned identity、阶段和历史检查，无新增导出符号或 WLAN patch。参考 native getter 源文件：`qca-wifi-host-cmn/umac/mlme/vdev_mgr/dispatcher/src/wlan_vdev_mgr_api.c`。

同时复核 Leekin2/XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb` 的 `module/action.sh`，继续保留原厂 CNSS2 和手动部署/恢复合同。

## 实现

- `mishare_runtime_bssid_bind` 只对精确 owner/VDEV cookie、owned ref/events、未关闭/无错误状态工作；有 MC work 时返回 EINPROGRESS，不在回执发布期间接触组件。
- 首次绑定只允许 fresh PAS/INIT、未 native CREATE/PE/rate/radio 的 owned VDEV。其 MLME 组件已由 runtime attach 创建，但尚未发固件 CREATE；在这一步绑定比上游 adapter-start 后更早，避免配置到错误生命周期实例。实际 CREATE/PE/channel/rate 代码随后必须保留同一字段。
- 在 native 写入前冻结 requested/value；验证同一 MLME/VDEV、type/subtype、opmode 和初始状态，再复制到 `mgmt.generic.bssid` 并读回，成功才记录 applied。这个 applied 只表示 host metadata 写入/读回。
- 同值轮询不重写字段；改值 EBUSY，实际字段漂移或组件矛盾记录 sticky error 并封锁 owner，禁止通过重写悄悄修复或直接普通退出。初始忙/关闭/无归属不会创建绑定记录。
- 新 host bind API 沿用 RTNL、原始 parent identity、context 和 DOWN 检查。request bridge 从自身冻结快照取 BSSID，绑定成功后才调用原 prestart；等待不记为永久错误，失败保留 authoritative host 槽。
- 不修改 PE `bssId`、self MAC 或 self-peer 地址。原 PE helper 仍按 self MAC 建会话和检查删除身份，与上游 setter→按 MAC 创建 PE 的关系一致。该操作不占用新 timer/DP/firmware 资源，退出沿用原 host/NDI 生命周期，不增设第二条释放路线。

## 验证

100 项本地 Python 回归、语法/diff 和新 native 组合源码生成通过；本地未编译大 native fixture。

新增 BSSID native 组合基于 0161 的生产 prestart/runtime/rate owned-MC 与 selected native cleanup：先绑定非零 BSSID，再贯穿原 512 组准备/部分速率失败/普通退出组合和 12 组发布失败/flush/隔离场景。每次 controller poll 检查字段与 owned 记录一致，PE 保持 MAC identity，最终仍经原生 SM/VDEV free。

11 项额外边界：纯 host 绑定/同值/改值/退出、缺引用、draining、过晚首次绑定、subtype/type/MLME owner/state 矛盾、SSR 封锁、实际字段漂移，以及真实 work reservation 等待后归还并绑定零字节 metadata。零值案例只证明原生 setter 的字节合同，不证明该 BSSID 具备无线有效性。三项 native 变异去掉实际写入、改值拒绝或读回验证，要求行为断言失败。

旧模型的 MLME BSSID 字段下移至共同平台布局，START-plan/WMA 模型只保留一份该字段；未改变真实内核布局。request bridge 模型新增 frozen BSSID 来源、等待恢复及错误保留场景；host fixture 增加新 runtime API 的显式模型 stub，完整目标编译仍验证真正字段/API。

新组合与变异、原有回归和实际 WLAN 编译待 Actions。0163 的 controller 与 stop-admission 已 success，其他作业仍有在途；不记作全门禁完成。

## 未完成内容

此处没有向 firmware 发送 BSSID/滤波命令，也没有 START-plan/START/UP，因此不能声称 firmware、RX filter 或 Apple 发现已使用该 BSSID。retry、聚合、完整 managed config、自动 parent lease 和端到端互通仍未完成。公开初始化和 START 保持关闭，无新手机包或操作。
