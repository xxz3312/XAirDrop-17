# 0141：Wonder 桥接的 host 会话控制器

本轮新增内部 `mishare_bridge` 控制器，将已有 host 分配、runtime 附着、异步 radio START 和退出串成一条保留所有权的调用链。尚未安装到公开 Wonder 回调，手机无需操作。

## 上游依据

- Weverses/OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d`：`kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch`（blob `8874b020b4d7eadea41adea787d53dcca08a3c62`）。重新核对 `wlan_hdd_wondertap_init/deinit` 的参数检查、RTNL、vdev sync、接口创建、信道和退出顺序。上游初始化还处理国家码、速率、重试、过滤和数据面，不能用 radio UP 替代它的完整结果。
- Leekin2/XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb`：`module/action.sh`（blob `024cd17fb19c50c10f204552f8a2cd6fffc5d30a`）。继续保留原厂 CNSS2 和手动试验入口，本轮没有修改设备端加载或开机策略。

差异：popsicle 已有异步 NDI/runtime 生命周期，不能直接套用上游同步全局 `g_wt_ctx` 的释放方式。本控制器使用明确的 host 所有权槽，失败不丢失资源，不在锁内等待完成，不重放失败阶段。

## 行为

1. 控制器必须零初始化一次；首次提交固定 HDD、MAC、频点和平台验证后的 NSS。
2. 依次创建 DOWN host、附着 runtime、推进已有 session。前两步只返回 EINPROGRESS；会话提交被接受也不代表完成。
3. HDD/MAC/频点/NSS 改变返回 EBUSY；任一启动阶段失败后保留首次错误和 host，不自动重试或重建。
4. retire 永久关闭新启动，直接传递权威 host 槽给 destroy。EINPROGRESS/失败保留其返回后的所有权，后续只能继续退出。
5. destroy 返回成功但仍留 host，或返回错误却清空 host，均视为合同破坏，返回 EUCLEAN 且不再自动调用 destroy。未被本控制器接管的外来 host 不释放。
6. 只有 destroy 确认结束且 host 为空才完成 retire。关闭后的控制器不复用。

## 验证与边界

- 本地 100 项 Python 回归通过；Python 语法和 diff 空白检查通过。
- C 编译仅在 Actions 执行。新增独立 bridge-controller 作业，对实际控制器头文件运行 ASan/UBSan 模型，覆盖一次分配、分阶段推进、配置变更拒绝、启动各阶段故障、等待/失败后继续退出、错误所有权合同以及空控制器退出；同时运行已有 session fixture。
- 新头文件随 CI setup 复制到真实 WLAN，由 host.c 包含，完整目标编译继续检查真实头文件兼容性。
- 模型中的 host、锁、父级寿命和完成事件并非真实内核。这个对象不获取父级租约；调用者仍须持 RTNL/PSOC transition，并在每次异步调用之间保留同一 HDD/组件/固件生命周期。
- 没有自动 worker、公开 Wonder 回调连接或新手机包。当前 backend init 仍为 EOPNOTSUPP。radio UP 不代表 RX/TX、AWDL 或 Apple 就绪。

下一步：补齐实际 native 父级生命周期协调，再映射 Wonder 初始化的国家码、速率/重试、过滤和收发参数，并将 typed init/poll/retire 接到本控制器。不能在父级协调完成前启用现有 attach 参数来绕过此边界。
