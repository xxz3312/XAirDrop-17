# 0156：原始 SSR 封锁后记录真实 VDEV DELETE 回执

0155 八项必选 CI 已全部通过（Actions 42405410946）。本阶段解决普通 VDEV DELETE 已成功返回、尚待原生回执时先发生 SSR，随后有效回执被 blocked 标记忽略的问题。只新增受限的观察与衔接，不发送或补造 DELETE ACK；公开 init/START 继续关闭，手机无需操作。

## 上游和原生来源

本轮重新读取 Weverses/OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` 的 `kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch`（blob `8874b020b4d7eadea41adea787d53dcca08a3c62`）：保留先等待 teardown 完成再释放 adapter 的顺序。重新读取 Leekin2/XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb` 的 `module/action.sh`（blob `024cd17fb19c50c10f204552f8a2cd6fffc5d30a`）的恢复路径，保持 stock CNSS2 和现有手动部署边界。

同步上游没有本项目独立异步 owner 的原始 fence/回执记账。本轮核对现有锁定 MiCode WLAN `36df473046706a5259942e1bf7222108dbbb860f` 的 owned DELETE reply origin：原生 timer/PM 清理完成后才通知 runtime。继续通过该真实函数来源记录事实，不将 WMI 发送成功或 SSR 封锁视作 ACK。

## 行为

- 原始 quiesce 首次选择 SSR 时，在相同 registry 锁内先核对健康的 host/NDI、可信已完成速率回执、ordinary admission、PE/peer 删除完成、VDEV DELETE pending 且 native send 已成功返回、尚无 DP/context 释放尝试，再设置 late_delete_armed。
- 第一停机原因不是 SSR、此前已有 blocked/错误、send 返回未结束/失败、身份与完成记录不完整的对象不能 armed。后续再次 quiesce 不补发资格。
- 普通非封锁路径保持原行为。SSR 封锁后的原生 firmware DELETE 回执仅在 armed 和当前 in-flight 形状仍完整、无 sticky 错误时记录 delete_replied/late_delete_reply。blocked、quiesced、原始 receipt 和错误均不清除。
- 窗口从未开放或已经关闭时，仍可记录真实晚到事实；这不会授予释放资格。后续仍要经过 0155 的 native window、MC 排空、DP helper 身份/物理 peer 检查和 DP final-free，关窗则保留。
- 非 firmware/timeout、匹配的重复 VDEV 完成保持 sticky completion_error。匹配的无效/重复 peer 通知也记录同一错误，避免 SSR 已经置位 blocked 后掩盖新的异常。外来 PSOC/ID/token 保持忽略，不采用其他对象的回执。

## 验证

本地实际 scalar rate/准入代码、17 项变异检查及 100 项 Python 回归通过，语法和 diff 检查通过。native composition 从锁定源生成，本地不编译。

新增独立 Actions-only 原生组合：两个频段 × 四种速率结果 × 16 种回调组合 × direct/batch，共 256 组。实际选择体的 DELETE reply/timer/PM origin 在原始 SSR fence 后执行，再衔接原生首次 DP submit、DP final-free、WMA/legacy finish 和 host final-free。10 类保留场景覆盖 fence 前异常、首因 REMOVE、send 证据缺失、timeout、重复 VDEV/peer、关窗、回执缺失、外来 PSOC 以及 receipt 完整性错误。三个原生变异控制分别移除 armed 记录、延迟回执分支或封锁前健康检查。新增 native 组合及三个变异控制已通过 Actions 42408125741、stop-admission 作业 128510161200 的独立步骤 Native late DELETE reply across SSR with sanitizers。其余生命周期回归和完整目标构建仍在运行，不提前计为全部 CI 通过。

firmware 回执到达、物理 transport/DP/peer/ref/lock 原语仍是模型；caller/fixture 持有原生父级。没有收到真实 DELETE reply 的对象仍不恢复，未覆盖更早 PE/peer 回执中断、配置后 START/UP、自动完整 parent lease 或手机/RF/Apple 互通。无手机安装包。
