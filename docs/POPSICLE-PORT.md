# 小米 17 Pro Max 适配进度

目标是为 `popsicle / canoe / SM8850` 移植 AWDL，再接入小米互传。
当前没有可安装的小米 17 适配包，也没有实机收发成功的结论。
上游 OPAirDrop 的 Oplus `sun / SM8750 / 6.6` 安装包不适用于此设备。

## 本次仓库迁移

此前临时工作区中的修改和构建输出已丢失，未推送的本地提交不能恢复。
本次根据保留的调查记录重建部分文件，不声称完整恢复旧提交。
新增脚本、工具链和下述编译检查在当前环境重新执行；旧内核构建结果不作为新文件的验证结果。

已重建：

- Android 6.12 ELF 导出读取修复：根据 relocation 的 `sh_info` 找目标节，
  不再依赖 `.rela___ksymtab+...` 的旧命名。
- `tools/kernel/popsicle_preflight.py`：只读比较原厂/候选模块与真实导出表，
  检查模块身份、vermagic、冲突和缺项；全部匹配仍只代表 CRC 证据。
- provider/probe 的实验性 Kbuild 入口。
- `kernel/popsicle-availability/`：参考 XAirDrop 的 6.12 sysctl 源码，
  默认关闭、没有空末尾条目。仅提供可用性节点，不实现无线通道。
- 最小 `hwid.h` 声明及出处；必须重新验证原厂 ABI 后才能用于候选构建。

两个 WLAN 源码补丁和诊断构建入口现已重建，见 [诊断构建说明](POPSICLE-BUILD.md)。
补丁已在锁定的小米源码上核对；完整模块构建和无线运行仍未验证。

## 已记录的目标基线

| 项目 | 此前采集值 |
| --- | --- |
| 系统 | OS4.0.5.0.XPBCNXM / API 37 |
| 内核 | 6.12.69-android16-6-g43b5ab7e247d-abogki558343811-4k |
| 原厂 WLAN | qca_cld3_peach_v2 / 5.2.1.146N |
| WLAN SHA256 | 202977cadf13b330a21838f3dd222cb0886eb0649d705937a778d7da69085f75 |
| 模块特征 | 4K、KCFI、MODVERSIONS、EXTENDED_MODVERSIONS、GENDWARFKSYMS |

公开 WLAN 源码是 5.2.1.137C，与原厂不同。候选 ACK R62 的版本号相同，
但不是原厂精确提交，仍有 Xiaomi 配置差异。
此前记录：使用官方实际 vmlinux.symvers 与原厂依赖模块导出，原厂 WLAN
610 条版本记录全部有匹配且无 CRC 冲突。这个结论针对原厂二进制，不能证明重编驱动可加载。
原始诊断包、vendor_boot、设备日志和厂商二进制不上传到此公开仓库。

## XAirDrop 参考范围

参考 [Leekin2/XAirDrop](https://github.com/Leekin2/XAirDrop/tree/eb1fe215c6473a8dbcc6edf6cf1e67d93f250f76)：

- 面向小米 15 / 15 Ultra，内核 6.6.118，不是小米 17 的驱动适配。
- 可参考 DomesticXOsComm/libxos、XOS Binder 客户端、原生互传 APK 接入、
  蓝牙广播、会话 Wi-Fi 管理与 root 网络注册助手。
- APK 补丁锁定具体 SHA256，不能只看 5.4.2 版本号；不能直接套用机型专用分享面板补丁。
- `patchcrc.py` / `fixmodlayout.py` 的二进制改写不是 ABI 兼容证明，
  不用于强行加载 6.6 驱动到 6.12。
- `patch_libxos.py` 把不支持的 SET_FEATURES 返回值改成成功，
  必须先核对所需命令和真实功能，不能据此判断底层支持完整。
- 该提交 README 报告小米 15 向 iPhone 发送成功，明确说明从 iPhone 接收尚不可用。

## 离线审计

```sh
python3 tools/kernel/popsicle_preflight.py \
  --stock /path/to/stock/qca_cld3_peach_v2.ko \
  --kernel-symvers /path/to/actual/vmlinux.symvers \
  --dependency /path/to/stock/cfg80211.ko \
  --dependency /path/to/stock/cnss2.ko \
  --out /path/to/audit.json
```

对每个真实原厂依赖重复 `--dependency`；可加 `--candidate` 检查重编模块。
不要从原厂导入的期望 CRC 拼接假的 Module.symvers。
退出码 0 仅表示所提供 CRC 证据无冲突、无版本记录缺项、无未带版本记录的未定义符号；
1 拒绝、2 不完整、3 输入错误。候选模块完全缺少版本证据时直接拒绝。
这不是可加载性检查。

## 本轮复核

重新下载原厂基线包、官方 CI 真实 `vmlinux.symvers`，匹配原厂 WLAN 的 SHA256。
当前恢复的 14 个其他 vendor 模块加官方核心导出，覆盖 562/610 条记录，
CRC 冲突为 0，缺少 48 条，审计状态为 `INCOMPLETE`。
此前 610/610 的记录依赖额外采集包和 vendor_boot 中的依赖模块，本次尚未恢复。
可公开复核的汇总见 [审计记录](research/popsicle-baseline-recovery.json)。

本轮 `modules_prepare` 已通过，保留原厂关键配置和 Clang/Rust/bindgen 身份；
仍有 12 项其他配置差异，不能称为原厂等价内核。Ubuntu bindgen 0.66.1 曾在
Rust 绑定生成时崩溃，现锁定官方 0.69.5，并验证旧版本会被配置检查拒绝。
Wonder、provider、绑定探针、可用性节点的对象编译已通过；这不是 `.ko` 或无线功能验证。
最小 HWID 声明已通过签名探针与原厂 WLAN 调用者 CRC 对照，并复核原厂 country 判断指令。

WLAN 基线对象编译与链接已通过，目录中生成 792 个对象文件，输出
`qca_cld3_peach_v2.o`。未执行完整模块 modpost 或加载测试。候选对象的
574 个未定义 ELF 符号与原厂 `.ko` 的 609 个存在差异；对象还会引用后续
模块生成阶段提供的 `__this_module`，因此这个对照不是 ABI 通过结论。

特别是候选对象新增引用 `cnss_get_wlan_tsf_gpio`，当前采集的原厂 CNSS2
导出表中不存在该接口。公开源码的 `platform/cnss2/power.c` 有对应实现，
但不能把它的私有结构或整个 CNSS2 模块直接套到原厂系统。
应先厘清匹配的 WLAN/CNSS 源码与 DDK 配置，不能添加假成功实现来消除未解析符号。

进一步源码检查表明，canoe 配置选择 TSF NOIRQ，GPIO IRQ 调用分支没有启用，
但 PLD helper 仍被无条件编译。第三个补丁按实际分支条件裁剪 helper，
保留启用 GPIO IRQ 时的原实现；由新的 [Actions 工作流](POPSICLE-ACTIONS.md)
执行补丁后的全新编译和符号检查。首轮已成功完成，CNSS 所需名称 72/72
均有原厂 provider 导出，原先 GPIO helper 引入的缺项已在该检查中消除。
结果仍只是名称覆盖，后续继续检查完整模块、CRC/类型/结构及其他依赖。
[首轮验证记录](research/popsicle-actions-first-pass.json)。后续编译使用 GitHub Actions。

## 下一步

新的 Actions 默认阶段已扩展为 `module-trial`：先生成辅助模块的完整诊断 `.ko`，
严格执行 modpost，再比较版本记录与模块头部三项参考，并检查 WLAN 全部依赖名称。
第一轮严格检查已生成 `wonder_sysctl.ko`，6 条版本记录及 1600/392/1528
头部参考均匹配，未带版本的未定义符号为 0。原始严格比较因发布前缀不同而停止，
随后根据参考内核对 basic CRC 的规则只读重分类为 `REVIEW_KERNEL_RELEASE`，
不修改原始模块。BTF 因缺少 vmlinux 未生成，后续模块及 WLAN 完整依赖仍待新运行。
[严格检查记录](research/popsicle-module-trial-1.json)。目前不能称为 ABI 或可加载性通过。

1. 解决新增 CNSS 接口缺失及公开源码/DDK 配置差异，补齐真实依赖导出证据，进行完整模块与结构检查。
2. 在 Xiaomi WLAN 中移植 Wonder provider、接口生命周期、WMI TX、monitor/native RX。
3. 核对固件命令和用户态 XOS 协议后再接入互传，最后进行 Wi-Fi 与真实收发测试。

当前不生成安装包、不发布 Release、不放宽 Oplus 安装限制来冒充小米适配。
