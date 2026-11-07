# 0149：有所有权跟踪的 MC 速率批次与原生 WMA 直接提交

0147（42368694662）和 0148（42370003141）的全部八项必选 CI 均已成功，包括完整 WLAN 编译、严格链接、布局和新增 host 支持合同检查。本轮将固定速率的异步工作接入既有 runtime 工作计数，仍无公开初始化或手机操作入口。

## 上游及原生依据

- 本轮重新读取 Weverses/OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` 的 `kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch`（blob `8874b020b4d7eadea41adea787d53dcca08a3c62`），保留 native rate 编码和 fixed-rate→GI→HT20 的顺序。
- 本轮重新读取 Leekin2/XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb` 的 `module/action.sh`（blob `024cd17fb19c50c10f204552f8a2cd6fffc5d30a`），维持保留原厂 CNSS2 和手动加载边界，不改设备端脚本。
- 核对 MiCode WLAN `36df473046706a5259942e1bf7222108dbbb860f` 的 `wma_main.c`：`wma_cli_set_command` 委托 `wma_cli_set2_command` 投递 WMA_CLI_SET_CMD；实际 `wma_process_cli_set_cmd` 为 void，CLI 返回值不能报告其中的 WMI 提交错误。
- 核对 `wma_dev_if.c` 的 `wma_vdev_set_param` 直接调用 `wmi_unified_vdev_set_param_send`，返回真实 native 提交状态。本项目既有 PE/channel/start-plan 的 TARGET_IF MC callback、flush、VDEV ref 和 runtime work_get/enter/exit/put 顺序作为所有权接入模式。

偏离上游 CLI 二次排队的原因：原始消息只按 VDEV ID 排队，没有本项目 owner 工作计数，不能把它当成已纳入 owned drain 的消息。新路径不修改普通 CLI 行为，增加受限的 private MC/WMA 入口，避免再产生一条无法跟踪的 CLI 消息。

## 工作与提交合同

- `mishare_rate_post` 只接受已有 runtime owner、固定速率参数及内部完成函数。先做共享支持检查，按有效字段复制请求，取得额外 VDEV 引用及 runtime work reservation，再投递到既有 TARGET_IF MC callback 队列。
- 队列处理时先 work_enter；quiesce/drain 已封锁时只报告 ESHUTDOWN，flush 只报告 ECANCELED，二者不触发速率执行。进入成功的批次执行完整三步，保留首次错误和 attempted/submitted 位，不重发部分失败的批次。
- 每条 MC 命令使用真实 private WMA 入口，重新检查当前 WMA handle、同一 PSOC、VDEV ID 范围、精确 interface.vdev 指针、native VDEV 有效性及 PASSTHRU/NDI MLME 身份。只允许 fixed-rate、SGI 和 HT20 三项参数；返回 `wma_vdev_set_param` 的实际提交状态，不另排 CLI 消息。
- 完成时先退出 active work，释放请求内存并清空消息 body，再发布完整 receipt；发布期间 reservation 和额外 VDEV 引用仍持有。随后 work_put，最后还 VDEV 引用。空 body 再次 flush 返回错误，不重复发布或释放。
- 预发布分配/引用/工作 admission/队列拒绝逆序释放，无完成回调。原生 scheduler 的失败仅发生在发布前；成功可能已同步执行完成函数，post 返回后不能再解引用请求。
- caller 必须在 post 前建立自己的 one-shot 状态，并保持完成函数代码、owner 和父级/固件生命周期直到 owned work 排空；完成函数只借用栈上 receipt，应立即复制，禁止在回调中同步等待工作排空或销毁。已有 runtime owner 持有的 module 和 VDEV 生命周期规则继续适用。

本轮没有把新 post 入口连接到 runtime 的配置阶段状态机或 managed/public init；原 private CLI submit primitive 仍无自动 caller。没有自动重试、配置回滚、国家码修改、BSSID/重试/聚合/过滤/收发接入，也没有新增完整父级租约。分配引用和工作计数不等于硬件/组件/固件存活；仍须依赖并补齐 native parent teardown 协调。complete 只表示各步提交被接受，不是固件 ACK、参数生效、射频或 Apple 互通。

## 验证

- 实际 rate executor、shared rate checker 和新增 WMA helper 在模型环境执行：原 CLI 和 MC direct 两种提交路径共 384 组速率/失败场景；检查禁止 MC 路径嵌套 CLI 排队，以及 native WMA/PSOC/interface 身份和受限参数拒绝。
- 六项原执行器变异控制、四项 native WMA 身份/错误传播变异控制、五项工作所有权变异控制均触发行为断言。删除门禁必须编译成功后失败，不能用编译错误代替行为证明。
- 实际 rate_work C 另测 NULL/畸形输入、四种预发布错误、排队、同步完成、flush、执行前封锁、执行错误、输入被 caller 修改后的快照及重复 flush。检查 callback 时 reservation/VDEV ref 保持，最终计数与内存平衡。
- ASan/UBSan 和 100 项本地 Python 回归通过；本地 ptrace 下关闭 LeakSanitizer，Actions 开启。runtime admission/ref/scheduler/WMI 在新 wrapper fixture 中仍为模型，未完成 native runtime 与物理 shutdown 的端到端验收。
- 0065→0066 对原生 WMA 文件/Kbuild 顺序 apply 检查通过。新对象、WMA include、复制入口、四个必须存在的链接符号、两份 fixture 和报告接入 CI。实际目标编译、原生类型/头依赖与严格链接待本轮 CI，不计实机验收。
