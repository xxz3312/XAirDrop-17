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
结合 17 个原厂 provider 的 1110 条真实导出（含 GPL 类型与命名空间）供 modpost 使用。
GKI 保护模块列表按锁定 common 源码中的官方定义生成，不关闭保护配置。
原厂模块头部参考为 1600 字节，init/exit 指针偏移为 392/1528；只比较这三项
不能验证全部结构布局。模块版本记录由 modpost 从 provider 表复制，匹配也不能
独立证明调用者 C 类型与被调用者一致。

先构建可用性、provider/探针、Wonder 的完整诊断 `.ko`；再检查 WLAN 全部外部符号。
缺少真实 provider 时状态为 `BLOCKED_MISSING_WLAN_EXPORTS` 并失败，
不会给未解析符号编造 CRC、添加假成功实现或改为告警放行。
HWID、IPA、IOMMU、QMI 等原厂导出已从补充采集恢复，待新一轮 Actions 完成严格链接。
日志也会明确记录模块 BTF 是否实际生成。

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

## 上轮阻塞与已恢复的输入

[运行 40219646880](https://github.com/xxz3312/XAirDrop-17/actions/runs/40219646880)
已完成对象编译、72/72 CNSS 名称检查，以及全部 4 个辅助模块的严格 modpost 和链接。
失败点是 WLAN 完整依赖检查，状态为 `BLOCKED_MISSING_WLAN_EXPORTS`，共缺 33 项。
完整报告见 [本次诊断记录](research/popsicle-actions-module-blocked.json)。

补充包 `17pm-airdrop-extra-20261025-162440.tar.gz` 已重新提供并核对为同一系统、
内核与槽位。已提取 `ipam`、`qmi_helpers`、`hwid`、`qcom_iommu_util`、
`qcom_va_minidump`、`rproc_qcom_common`、`powerinsight_interface`、`sched-walt`
这 8 个原厂 provider 的真实 CRC、导出类型与命名空间。
其中 ramdisk 模块来自包内的原厂 `vendor_boot.img`，未修改镜像或模块。

上轮 33 项缺失接口现已全部覆盖；原厂 WLAN 的 610 条版本记录亦全部找到真实
provider，CRC 冲突为 0。记录与原始文件哈希见
[补充包恢复报告](research/popsicle-extra-provider-recovery.json)。
只将导出元数据提交到公开仓库，原厂二进制保留在本地分析目录。
下一轮由 Actions 继续严格 WLAN 模块链接，仍须检查候选模块实际生成结果。
4 个辅助模块仍存在发布字符串差异，且没有生成 BTF；链接完成不表示可加载。

## 完整链接结果与审核阻断

[运行 40224797722](https://github.com/xxz3312/XAirDrop-17/actions/runs/40224797722)
已生成全部 5 个诊断 `.ko`，包括 `qca_cld3_peach_v2.ko`。
WLAN 未解析依赖为 0，573 条生成的版本记录均与输入 provider 表相符，
模块头部的三项参考字段也一致。完整记录见
[完整链接报告](research/popsicle-actions-full-link.json)。这仍不是独立的类型或运行兼容性证明。

该运行最终 exit 2 来自 `REVIEW_KERNEL_RELEASE`，并非编译器或链接器报错。
候选 vermagic 的发布标识为 `6.12.69-4k-ge2b8ca7c8d05`，
原厂模块为 `6.12.69-android16-6-4k`；其余标志一致，但需要继续核对原厂加载规则。
由于没有用于该构建的基础 `vmlinux`，模块 BTF 也未生成。
日志中的 WALT 源文件 grep 缺失没有阻止本次链接，不能当作最终失败原因。

工作流现将严格链接与兼容性审核拆成两个步骤：
`modules --link-only` 只允许完整链接且无硬性拒绝的结果通过构建步骤；
紧接着必须执行 `review`，发布标识待审核时仍会返回 2，并给出明确错误注释。
默认 `modules` 命令仍保留原来的审核退出行为。未添加 continue-on-error、
未改写 vermagic、未关闭严格 modpost，也未将待审核状态改为兼容性通过。
因此新工作流仍可能标红，但会明确显示失败的是兼容性审核，而非编译链接。

## 独立的结构布局核对

已下载并校验运行 40226040284 的 Artifact SHA256，从其 WLAN `.ko` 的 DWARF
用 pahole 1.25 导出独立 BTF 元数据，再与手机补充包中的原厂内核 BTF 比较。
导出前后候选 `.ko` SHA256 一致，没有改写模块或把原厂 BTF 注入候选模块。

7 个选定结构的直接布局全部一致：`module`、`net_device`、`wiphy`、
`wireless_dev`、`sk_buff`、`cfg80211_chan_def`、`ieee80211_channel`。
比较包含结构大小、直接成员的偏移、位域宽度、值类型大小和数组长度。
原厂选定布局元数据保存在 `kernel/abi/popsicle-stock-btf-layouts.json`；
不提交原厂 BTF 或模块二进制。结果见
[布局核对记录](research/popsicle-selected-layout-audit.json)。

探索检查还发现 969 个同名结构中有 968 个直接布局一致；唯一不同的 `fw_state`
分别来自内核 firmware_loader 和 WLAN HDD，是用途不同的私有结构。
仅凭 C 标签同名不能建立 ABI 对应关系，因此该探索结果不作为自动放行依据。

Actions 在严格链接后新增 `layouts` 步骤，自动导出候选元数据并核对上述 7 项。
类型缺失、歧义或直接布局不同会使该步骤失败。输出 `selected-layouts.json`
随诊断报告保存；检查通过只标为 `SELECTED_LAYOUTS_MATCH_ONLY`。
不递归核对匿名嵌套结构或指针目标，也未验证函数原型、KCFI、运行加载或无线固件。
这种独立元数据不等于生成可加载模块所需的、与基础内核关联的 split BTF。
发布标识审核仍保留，下一轮即使布局检查通过，整体 Actions 仍会在 `review` 标红。

## KCFI 审计与下一份必要输入

从实际原厂 WLAN 和 Actions 候选 WLAN 的 ELF 符号表读取绝对
`__kcfi_typeid_*`，并与 llvm-nm 的结果独立交叉核对。
原厂有 1090 项，候选有 1054 项，共有 1053 项中 1051 项相同、2 项不同：
`dp_prealloc_get_page_pool`、`hdd_roam_vdev_mac_addr_update`。
真实标识与来源哈希保存在 [原厂元数据](research/popsicle-stock-wlan-kcfi.json)，
结果及候选声明见 [KCFI 审计](research/popsicle-wlan-kcfi-audit.json)。

两项在候选源码中分别赋给 WLAN 内部 `ol_if_ops.dp_get_page_pool` 和
`mlo_osif_ext_ops.mlo_roam_osif_update_mac_addr`，声明与候选调用参数一致；
这两个函数名都不是原厂或候选模块的导出符号。
仅此不能认定跨模块 ABI 失败，也不能由哈希反推出原厂精确原型。
原厂 WLAN 没有 DWARF 或 BTF 调试类型，因此暂不能继续比较其精确函数声明。
审计工具为 `tools/kernel/kcfi_audit.py`；输出明确保留类型标识差异，未修改 hash。

下一步核对模块加载器需要与采集记录相同系统、当前活动槽位的 **boot.img**。
已有包的 `vendor_boot.img` 不含主内核；原厂 BTF 能看到 `same_magic` 的
`has_crcs` 参数，但不包含该函数的机器指令，不能据此确认原厂比较行为。
获得 boot 内核后才能尝试解包、符号定位与加载规则反汇编；能否恢复符号仍需检查。
不要用不同版本的官方镜像代替当前活动内核，也不要为本次审计刷写分区。
本次只更新离线审计与记录，不修改 workflow 或触发新的编译。

## 当前 boot 的加载规则证据与修正

已核对新提供的活动槽位 `_b` boot：系统仍为 OS4.0.5.0.XPBCNXM，
内核版本与前两份采集一致。boot 中的原始 BTF 与手机之前导出的 BTF
SHA256 完全相同。没有修改 boot 或写入任何手机分区。

从 ARM64 Image 恢复 kallsyms 后，静态核对原厂 `same_magic` 的指令：
`has_crcs` 为真时对两份字符串执行以空格为分隔符的 `strcspn`，
跳过发布前缀，再调用 `strcmp` 比较其余内容。
调用点读取 `load_info` 偏移 0x74 的字段作为布尔条件；原厂 BTF 确认
该字段正是 `index.vers`，即 basic `__versions` 的索引。
因此具备 basic 版本记录且其余标志一致时，发布前缀不同本身并非加载器拒绝条件。

审计证据、输入哈希、函数字节和指令记录见
`kernel/abi/popsicle-stock-loader.json`，由模块头部配置中的 SHA256 固定。
`tools/kernel/verify_stock_loader.py` 可用同一 boot 重验记录字节。
原始 boot、完整内核和完整符号表不提交到公开仓库。

现在这种情况仅在有匹配目标系统的已核对原厂证据时，分类为
`RECORDED_LOADER_CHECKS_MATCH_ONLY`；没有证据仍为 `REVIEW_KERNEL_RELEASE`。
无 basic CRC、CRC 不匹配、头部差异或其余 vermagic 标志不同仍拒绝。
前文多次“仍会标红”的说明是修正前的历史行为，本节取代该预期。
没有改写任何模块的 vermagic 或 CRC，也没有关闭 modpost。

重查旧产物还发现实验 provider 重复导出了原厂 CNSS 已有的
`cnss_set_vendor_wonder_priv_data`。相同 CRC 不能允许重复符号提供者。
已把实验 provider 和其探针改用私有 `opairshare_set_wonder_priv_data`，
并让 CI 对辅助模块及 WLAN 的重复导出一律拒绝，即使 CRC 相同。
原厂 CNSS 接口与原厂导出元数据保持原样。
旧产物的只读重查记录见
[原厂加载规则复核](research/popsicle-stock-loader-replay.json)；旧模块组合不能供安装。

下一轮 Actions 将验证新的桥接符号和完整检查流程。
工作流通过只表示已记录的离线检查完成；函数原型、KCFI 差异的完整影响、
无线固件、加载和 AirDrop 收发仍需后续验证。
模块 BTF 未生成的事实仍记录；原厂 WLAN 自身也无 `.BTF`，
不能单凭这一项推断加载一定失败，它也不是此前 exit 2 的实际原因。
