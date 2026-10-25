# 小米 17 Pro Max 适配进度

目标是为 `popsicle / canoe / SM8850` 移植 AWDL，再接入小米互传。
当前没有可安装的小米 17 适配包，也没有实机收发成功的结论。
上游 OPAirDrop 的 Oplus `sun / SM8750 / 6.6` 安装包不适用于此设备。

## 本次仓库迁移

此前临时工作区中的修改和构建输出已丢失，未推送的本地提交不能恢复。
本次根据保留的调查记录重建部分文件，不声称完整恢复旧提交。
新增脚本只在当前环境进行主机检查；旧内核构建结果不作为新文件的验证结果。

已重建：

- Android 6.12 ELF 导出读取修复：根据 relocation 的 `sh_info` 找目标节，
  不再依赖 `.rela___ksymtab+...` 的旧命名。
- `tools/kernel/popsicle_preflight.py`：只读比较原厂/候选模块与真实导出表，
  检查模块身份、vermagic、冲突和缺项；全部匹配仍只代表 CRC 证据。
- provider/probe 的实验性 Kbuild 入口。
- `kernel/popsicle-availability/`：参考 XAirDrop 的 6.12 sysctl 源码，
  默认关闭、没有空末尾条目。仅提供可用性节点，不实现无线通道。
- 最小 `hwid.h` 声明及出处；必须重新验证原厂 ABI 后才能用于候选构建。

旧的试编译脚本和两个 WLAN 源码补丁尚未恢复；不要把本次迁移当作完整可复现的驱动构建。

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
退出码 0 仅表示所提供 CRC 证据无冲突且无版本记录缺项；1 拒绝、2 不完整、3 输入错误。
这不是可加载性检查。

## 下一步

1. 重新获取锁定源码和原厂基线，恢复未完成的原厂 WLAN 编译，重做 ABI/结构检查。
2. 在 Xiaomi WLAN 中移植 Wonder provider、接口生命周期、WMI TX、monitor/native RX。
3. 核对固件命令和用户态 XOS 协议后再接入互传，最后进行 Wi-Fi 与真实收发测试。

当前不生成安装包、不发布 Release、不放宽 Oplus 安装限制来冒充小米适配。
