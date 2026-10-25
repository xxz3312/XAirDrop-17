# GitHub Actions 诊断构建

后续内核编译使用工作流 **Popsicle diagnostic build**：

https://github.com/xxz3312/XAirDrop-17/actions/workflows/popsicle-build.yml

修改相关源码、补丁、配置或构建入口后，推送到 `main` 自动触发。
也可进入工作流页面点 **Run workflow**：

- `wlan-object`：默认，准备内核并编译 WLAN、Wonder、provider、绑定探针和可用性节点对象。
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
压缩包不是 Root 模块，不包含可刷入的 `.ko` 或安装脚本，不发布 Release。

## 如何判断结果

编译成功后仍要检查 CNSS 接口。若候选对象引用的 `cnss_*` 名称不在原厂
provider 导出表中，该步骤退出失败并写明缺项，不会因编译成功而放行。
全部名称覆盖时状态仍为 `NAME_COVERAGE_ONLY`，不代表 CRC、结构布局、
KCFI、所有依赖、固件、加载或实际 AirDrop 收发已通过。

第三个源码补丁针对 NOIRQ 模式下无用的 GPIO IRQ 引用。
[首轮 Actions](https://github.com/xxz3312/XAirDrop-17/actions/runs/40215365901)
已全新编译成功；CNSS 名称检查为 72/72、缺项 0。
详细记录见 [首轮结果](research/popsicle-actions-first-pass.json)，仍不代表完整模块 ABI 或可加载性通过。

若 fork 的 Actions 尚未启用，需要先在仓库 Actions 页面启用工作流。
工作流只有 `contents: read` 权限，不会自行发布安装包或修改仓库。
