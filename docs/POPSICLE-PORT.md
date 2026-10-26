# 小米 17 Pro Max 适配进度

目标：popsicle / canoe / SM8850，OS4.0.5.0.XPBCNXM，Android API 37。
内核为 `6.12.69-android16-6-g43b5ab7e247d-abogki558343811-4k`。
当前没有可安装的 AirDrop 适配包，也没有无线收发成功的结论。

## 已完成的构建与静态核对

- GitHub Actions 完成 WLAN、Wonder、provider、probe、sysctl 的完整诊断模块链接。
- 工具链版本固定，Clang/Rust/bindgen 缓存在编译前保存。
- 原厂 WLAN 的 610 条版本记录全部找到真实 provider，CRC 冲突为 0。
- 候选 WLAN 的全部外部依赖通过严格 modpost；新增重复导出检查，即使 CRC 相同也拒绝。
- 7 个选定结构的大小、直接成员偏移与位域和原厂 BTF 相符。
- 从用户提供的当前 boot 的真实指令确认：存在 basic `__versions` 时，原厂加载器
  忽略 vermagic 的发布前缀，仍比较全部其余标志。证据已按哈希固定。
- 实验桥接接口已使用私有名称，避免与原厂 CNSS 同名导出冲突。

成功完整构建：[Actions 40229703474](https://github.com/xxz3312/XAirDrop-17/actions/runs/40229703474)。
构建与证据边界见 [Actions 说明](POPSICLE-ACTIONS.md)。这些离线检查不是完整 ABI 或运行认证。

## 已完成的实机测试

| 阶段 | 实测结果 | 证据 |
| --- | --- | --- |
| 最小 sysctl 模块 | 加载成功，节点默认值 0，正常卸载 | [第一阶段记录](research/popsicle-sysctl-device-pass.json) |
| 私有 provider/probe | 重复注册、竞争注册检查成功，清除回调并按顺序卸载 | [第二阶段记录](research/popsicle-provider-device-pass.json) |
| Wonder 主模块 | 硬件注册、初次绑定、操作表注销、重新绑定及卸载通过 | [第三阶段记录](research/popsicle-master-device-pass.json) |

以上未替换原厂 WLAN，没有开启可用性开关。第三阶段退出码为 0，
Wonder/provider/probe 均无本次加载残留，前后网络接口名称一致。
原有 mac80211 保持加载。该测试未启动无线接口或执行收发。

## Wonder 主模块修复与验证记录

主模块在分配并注册虚拟无线硬件后，原代码遇到缺少 DT phandle 或组件绑定失败会直接返回，
没有对称释放硬件；debugfs 初始化也没有正确识别 ERR_PTR。
在进行主模块实机测试前，先修复这些失败路径：

- 组件匹配失败时释放 mac80211 硬件，保留实际错误码。
- debugfs 初始化失败时删除 component master，再释放硬件。
- DT provider 引用保持到组件拆除后才释放；清除 drvdata 和旧操作表指针。
- debugfs 目录/文件创建错误清理完整，重复退出不会保留旧指针。
- netdevice notifier 注册失败时回滚已注册硬件与 TX 状态队列。
- 只在本模块创建了平台设备时注销它。

修订后的原生模块已由 [Actions 40274658306](https://github.com/xxz3312/XAirDrop-17/actions/runs/40274658306)
编译并通过当前离线检查。第三阶段首次实机尝试在 mac80211 硬件分配阶段失败，
尚未完成主模块绑定；模块清理完成，接口名称未变化。
[失败记录](research/popsicle-master-device-failure.json) 已保存，
补采已确认原机 mac80211 文件与基线相同，但旧警告未保留。
对原机 allocator 指令和旧候选 ELF 回调重定位的核对确认 callback table 相差 16 字节：
外置无线模块的 `CONFIG_NL80211_TESTMODE` 与 GKI 配置不同。
首轮修订构建 40281240881 虽成功，但产物核对证明其仍是旧模块；
原因是编译设置误放在被 Kbuild 覆盖的 Makefile 中，未实际启用。
现已移至实际 Kbuild，并加入链接后真实 ELF 回调位置必过检查。
[Actions 40284559893](https://github.com/xxz3312/XAirDrop-17/actions/runs/40284559893)
已通过全部当前检查；下载原始产物后独立重验确认三个频道回调位置正确。
[修订产物报告](research/popsicle-master-rebuild-allocator-pass.json) 已记录，新版已通过目标设备绑定、解绑、重新绑定及卸载实测。
详见 [审计](research/popsicle-mac80211-allocator-audit.json)。旧测试包作废，新实机包只使用修订后的原始 Actions 模块。

## 下一步：真实 WLAN 后端

component 绑定问题已通过受限实测，后续重点转向 Xiaomi WLAN 驱动源码。
先核对真实接口创建/销毁、频道设置、发送完成通知和 monitor/native RX 的调用链，
再移植 Wonder 操作表；不能将 probe 的不支持返回值改成成功来充当实现。
在构建检查通过、失败路径与回滚明确之前，不进入原厂 WLAN 替换测试。

## 仍未完成

1. Xiaomi WLAN 中真正的 Wonder 操作表与接口生命周期、WMI TX、monitor/native RX。
   当前 probe 的无线 init 明确返回不支持，不能作为可工作的后端。
2. 固件命令与用户态 XOS 协议核对、原生互传接入。
3. Wi-Fi 共存与 iPhone 双向真实文件传输。

公开 WLAN 5.2.1.137C 与原厂 5.2.1.146N 不同，ACK R62 也不是原厂精确提交。
KCFI 审计在 1053 个共有标识中发现两项私有回调差异；候选内部声明相符，
但原厂模块缺少调试类型，仍不能还原其精确函数原型。

## 参考项目的适用范围

OPAirDrop 的 Oplus sun / SM8750 / 6.6 安装包不用于本机。
[XAirDrop 固定参考](https://github.com/Leekin2/XAirDrop/tree/eb1fe215c6473a8dbcc6edf6cf1e67d93f250f76)
面向小米 15 / 15 Ultra；可参考用户态接口与互传接入，但不能直接复用其 6.6 驱动。
不使用改 CRC、改模块布局、强制加载或假成功接口来冒充移植完成。
不发布未经运行验证的 Release。原厂 boot、完整内核、日志和厂商二进制不提交到公开仓库。
