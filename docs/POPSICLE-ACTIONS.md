# GitHub Actions 诊断构建

后续内核编译使用工作流 **Popsicle diagnostic build**：

https://github.com/xxz3312/XAirDrop-17/actions/workflows/popsicle-build.yml

修改相关源码、补丁、配置或构建入口后，推送到 `main` 自动触发。
也可进入工作流页面点 **Run workflow**：

- `module-trial`：默认，先完成对象编译和 CNSS 检查，再进行严格辅助模块链接、头部与版本记录检查，并检查 WLAN 的全部依赖名称。
- `wlan-object`：仅准备内核并编译 WLAN、Wonder、provider、绑定探针和可用性节点对象。
- `prepare`：只验证配置和 `modules_prepare`，不生成 WLAN 对象。

工作流使用 Ubuntu 24.04、锁定的源码提交、官方 Clang/Rust/bindgen，最多 4 个并行任务。
首次运行需下载较大的工具链，后续复用缓存。无须配置第三方下载地址或额外 Token。

Clang/Rust 与 bindgen 分别缓存，使用操作系统、架构和版本记录生成缓存键。
输入准备成功后、开始编译前立即保存，因此后续编译或接口检查失败也保留缓存。
命中缓存后跳过相应下载，并核对来源标记；bindgen 还会核对版本。
连续推送会排队等待当前构建完成，不会为更新缓存设置而取消正在下载的首轮构建。

## 输入与输出

`kernel/configs/popsicle-stock.config.gz` 只包含此前采集的内核配置，
按确定性 gzip 重新编码；解压内容 SHA256 在相邻 JSON 中。
此配置无构建盐和证书私钥。没有上传固件镜像、设备属性日志或原厂 `.ko`。
CI 的 CNSS 检查使用从真实原厂模块提取的 `cnss_*` 导出元数据，见
`kernel/abi/popsicle-stock-cnss-exports.json`。

每次运行上传 `popsicle-diagnostics-...` Artifact，保留 7 天，包括：

- 源码版本记录、配置差异和构建日志。
- 成功时的 `diagnostic-objects.tar.gz`，仅含诊断对象文件。
- WLAN 阶段成功后的 CNSS 接口检查报告。

失败后也会尽量保留已生成的日志和报告。下载入口在对应运行页面的 Artifacts 区域。
严格模块阶段还会尽量保存 `diagnostic-modules-not-for-install.tar.gz` 和
`module-trial.json`。其中可能包含诊断 `.ko`；它们未经加载、固件和无线验证，
不供安装。没有 Root 模块 ZIP 或安装脚本，不发布 Release。

## 如何判断结果

编译成功后仍要检查 CNSS 接口。若候选对象引用的 `cnss_*` 名称不在原厂
provider 导出表中，该步骤退出失败并写明缺项，不会因编译成功而放行。
全部名称覆盖时状态仍为 `NAME_COVERAGE_ONLY`，不代表 CRC、结构布局、
KCFI、所有依赖、固件、加载或实际 AirDrop 收发已通过。

严格模块阶段从官方 CI 下载真实核心 `vmlinux.symvers` 并核对 SHA256，
结合 9 个原厂 provider 的 717 条真实导出（含 GPL 类型与命名空间）供 modpost 使用。
GKI 保护模块列表按锁定 common 源码中的官方定义生成，不关闭保护配置。
原厂模块头部参考为 1600 字节，init/exit 指针偏移为 392/1528；只比较这三项
不能验证全部结构布局。模块版本记录由 modpost 从 provider 表复制，匹配也不能
独立证明调用者 C 类型与被调用者一致。

先构建可用性、provider/探针、Wonder 的完整诊断 `.ko`；再检查 WLAN 全部外部符号。
缺少真实 provider 时状态为 `BLOCKED_MISSING_WLAN_EXPORTS` 并失败，
不会给未解析符号编造 CRC、添加假成功实现或改为告警放行。
当前原厂额外采集中的 HWID、IPA、IOMMU、QMI 导出尚未恢复，因此这一阶段可能因
真实证据不完整而停止。日志也会明确记录模块 BTF 是否实际生成。

参照 ACK 的 `kernel/module/version.c:same_magic`，只有存在 basic `__versions`
时才可在该比较中忽略发布字符串的版本前缀，SMP/抢占/架构等其余标志仍须一致。
前缀不同单独标为 `REVIEW_KERNEL_RELEASE`，保留原始字符串，不改二进制，
也不会给整个检查返回通过。只有扩展 CRC、没有 basic CRC 的模块不会套用此规则。
这是参考内核的比较规则，不是对原厂加载行为的实测。

第三个源码补丁针对 NOIRQ 模式下无用的 GPIO IRQ 引用。
[首轮 Actions](https://github.com/xxz3312/XAirDrop-17/actions/runs/40215365901)
已全新编译成功；CNSS 名称检查为 72/72、缺项 0。
详细记录见 [首轮结果](research/popsicle-actions-first-pass.json)，仍不代表完整模块 ABI 或可加载性通过。

若 fork 的 Actions 尚未启用，需要先在仓库 Actions 页面启用工作流。
工作流只有 `contents: read` 权限，不会自行发布安装包或修改仓库。

## 当前阻塞与恢复步骤

[运行 40219646880](https://github.com/xxz3312/XAirDrop-17/actions/runs/40219646880)
已完成对象编译、72/72 CNSS 名称检查，以及全部 4 个辅助模块的严格 modpost 和链接。
失败点是 WLAN 完整依赖检查，状态为 `BLOCKED_MISSING_WLAN_EXPORTS`，共缺 33 项。
完整报告见 [本次诊断记录](research/popsicle-actions-module-blocked.json)。

下一步需要恢复原先采集的 `17pm-airdrop-extra-20261025-162440.tar.gz`。
当前工作区没有该包；不必重新采集或上传整套系统固件。
如果原包已经找不到，则需要与基线相同系统版本的原厂 `hwid.ko`、`ipam.ko`、
`qcom_iommu_util.ko` 和 `qmi_helpers.ko`，以及用于确认来源的系统版本和内核版本。
这些名称对应待核对的 provider，只有实际解析导出表后才能确认覆盖情况。

恢复后先离线提取真实导出 CRC、类型与命名空间，核对来源、冲突和缺项，
仅将导出元数据更新进仓库，然后由 Actions 继续严格 WLAN 模块链接。
原厂二进制无需提交到公开仓库。输入补齐前重复运行同一工作流不会解决阻塞。
4 个辅助模块仍存在发布字符串差异，且没有生成 BTF；链接完成不表示可加载。
