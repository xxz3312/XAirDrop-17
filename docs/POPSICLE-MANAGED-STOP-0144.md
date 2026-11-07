# 0144：managed 停止入口与原生实例退出

将 netdev 停止通知、managed stop、HDD 私有实例和 0143 回执连接到同一条退出协议。通知只封闭入口并排队一次工作；工作线程不执行 managed 的 legacy 重启路径。存在错误或等待时继续保留 handle、绑定和模块引用。

## 参考

- Weverses/OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d`，`kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch`，blob `8874b020b4d7eadea41adea787d53dcca08a3c62`：复核 deinit、vdev sync、接口停止和 `g_wt_ctx` 释放顺序。
- Leekin2/XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb`，`module/action.sh`，blob `024cd17fb19c50c10f204552f8a2cd6fffc5d30a`：保留手动加载和原厂 CNSS2；设备脚本不变。

上游同步退出不能直接表示本项目已有的异步 runtime/回执等待。本轮只扩展同构建的私有 managed companion，不改变上游公开 ops/priv 或原厂 CNSS2 ABI。新私有回调字段要求配套重构建，不能混用旧 provider/Wonder/WLAN。

## 退出连接

- `wondertap_stop_managed` 封闭新启动，并在可选 `retire_process` 存在时，释放实例 mutex 后调用它；整个调用期间保持 DRAINING、精确 handle、绑定及模块引用。
- `managed_retire_inflight` 防止回调执行期间的普通 retire 或重复 stop 再次操作同一实例。quiesce/unbind 仍不能释放活跃绑定。回调返回后重新取得 mutex，检查状态/handle，再按既有结果合同完成或保留。
- 普通 provider quiesce 仍只封闭入口并检查所有权，不在 provider claim 锁中执行原生清理。legacy 和没有新回调的私有 backend 保持原路径。
- HDD 后端注册实际的 poll-only retire 和 process retire。前者只标记停止/查询完成，绝不等待原生锁或释放设备/实例；后者在规定的进程上下文推进清理。
- 新私有实例注册表按地址认证 token，在解引用前拒绝未知 token。busy 标志保护正在执行的实例，原生调用不持 registry 锁。实例持有独立模块文本 lease 和 device 分配引用；它们不是 HDD/组件/固件寿命保证。
- 进程退出先尝试消费已有回执；若仍 pending，在原生 scope 下移交 host，并在 registry 锁内核对 HDD/device/PSOC/PDEV 后，针对精确 serial 推进普通 host 清理，无需等待整个 WLAN idle 才能尝试回收。只在进入 scope 前的 EAGAIN/EBUSY 映射为等待；其他错误保留所有权。
- 精确回执清理不执行全局 module stop，不授权 SSR reset，也不清除隔离。已移交的 host 仍可由现有限定 SSR 路径退休；回执完成后，即使旧 HDD 上下文已消失，也可释放实例最后的 device/text 引用。
- 元数据工厂失败或 host 创建失败且没有 native owner 时，进程退出直接回收元数据，不访问旧 HDD。只有 host、回执和实例均真正释放后才返回 0 并清空 caller handle。

## 验证和未完成项

本地 100 项 Python 回归、Python 语法和 diff 检查通过。[Actions 42345877772](https://github.com/xxz3312/XAirDrop-17/actions/runs/42345877772) 的 bridge-controller 作业 `128323386512` 已通过，含 session/bridge/scope、managed、provider 和 legacy 六项 PASS_ONLY 标志；host/原生退出回归作业 `128323386501` 也已成功，包含实际 host、私有实例、runtime、执行控制器与原生生命周期模型；完整目标编译仍在运行。Actions 执行实际生产 C：Wonder 核心的锁外回调、回调内重入 retire/stop/quiesce/unbind、错误/假成功保留；真实 provider/master/worker 提取体；HDD 实例工厂失败、未知 token、busy、锁冲突、正常退出、runtime pending、移交后限定 SSR 和父级上下文消失后的完成。device/scope 引用与 host 父级引用使用独立模型账本。

实例工厂和 step 只有内部调用接口；公开 backend init 与 poll_start 仍返回 EOPNOTSUPP，没有用户可触发的创建入口。本轮没有安装包、自动重试计时器或射频启动。native primitive、父级、模块 API、固件事件和并发仍是模型，不能计为手机或硬件验证。

跨调用完整父级组件/固件租约、恢复开始前的 owner 协调、已提交 START/UP 的 SSR 回收、RX/TX 和 Apple 互通仍未完成。若 SSR 已经持有原生 transition，普通退出只能保留实例等待；不能绕过原有恢复门禁。下一阶段继续处理初始化的参数/父级 admission，再接公开 init/poll 与收发；手机保持当前状态，不重复 apply。
