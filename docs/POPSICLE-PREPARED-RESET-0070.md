# 0070：已 prepare、尚未创建 PE 的 NDI reset 回收

本轮扩展原有显式 SSR runtime 回收与 batch/host 入口，允许完整 legacy/WMA/self-peer 准备成功、但从未请求 PE/channel/START 的 INIT 会话进入 reset 清理。native shutdown 自动调用方仍未安装；PE、START、UP 和不完整准备状态继续保留。

## 回收顺序

原有 native CDS 窗口要求 SSR、owned MC 排空、HIF/HTC/RX 停止、WMI blocked 与事件 workqueue 排空。新路径还逐项核对原 psoc、attach-time DP cookie、PAS/NDI/INIT、WMA slot/ref/peer 数量、self-peer 的精确 vdev 归属。必须具备 DP peer force-detach 且未启用 peer-unmap confirmation，否则返回不支持并保留所有上下文。

能力和归属预检通过后，先执行专用 prepared 响应定时器同步取消/原生 deinit，避免定时器回调碰到后续释放的上下文。然后再次核对原生归属，调用现有 `wma_remove_peer(..., true)` 的无 firmware delete、force-detach 分支及原生 object-peer 删除；逻辑删除后还要在 vdev 锁内核对实际 peer count 归零，确保 peer 组件析构已经结束；若仍有延迟析构，则保留 WMA/legacy 并隔离该 owner。随后提交专用 prepared DP detach 并等待实际 DP final-free；WMA/legacy 在回调以及提交返回前始终保持。确认后才通过既有 helper 解绑 WMA、释放 legacy，最后等待对象实际 final-free 并释放 host。

每阶段的实际释放事实写回 owner；失败保留剩余资源并设置 sticky recovery_error，不重复删除。peer_create_attempted 等历史不清零，普通 peer/VDEV DELETE 提交/响应旗标不会被伪造。prepared 的定时器清理和上下文回收另有记录。范围外 PE/radio 会话没有通过改写状态机到 DOWN 来放行。

## 验证与限制

新增 Actions C 模型执行生产 runtime、原生 context helper、完整原生 `wma_remove_peer` 与 `wma_remove_objmgr_peer`、响应定时器及既有 DP/final-free 路径。覆盖同步/异步 DP callback、额外 final-free 引用、16 类能力/身份/状态/定时器拒绝、部分失败不重试和 PE/START/UP 拒绝；把 no_fw 改为 false 的负对照必须触发 WMI 断言失败。DP force detach、object peer 删除、QDF/内核同步和物理父资源仍为模型，不能证明目标固件/空口行为或 native 并发。

完整构建验证待 CI。本轮不创建手机测试包，HDD backend init 仍返回 EOPNOTSUPP。后续仍须接入原生 shutdown 协调、PE/UP 清理和完整 monitor，不能据此直接启用无线初始化。
