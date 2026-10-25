# 第一阶段实机测试：临时 sysctl 模块

当前目标仅是验证一个最小模块的加载、节点默认值和卸载。
这不是 AirDrop 安装包，没有 WLAN 驱动替换、自动启动或刷分区操作。

本阶段已在目标设备实测通过：节点默认值 0，退出码 0，模块卸载后不再归本脚本所有。
脱敏记录见 [实机结果](research/popsicle-sysctl-device-pass.json)。
下一阶段见 [provider/probe 测试](POPSICLE-PROVIDER-TEST.md)。

固定测试对象为 `wonder_sysctl.ko`，SHA256：
`b7ac3e8dd7d3544cfdfe67ea39b3b546fcc734897fe64478f20a88893532f625`。
成功运行 [40229703474](https://github.com/xxz3312/XAirDrop-17/actions/runs/40229703474)
的模块报告确认了同一 SHA256。测试包复用已下载且字节完全相同的 Actions 模块，
没有本地重新编译、去调试信息或修改版本字符串。

仅用于 popsicle、OS4.0.5.0.XPBCNXM、
`6.12.69-android16-6-g43b5ab7e247d-abogki558343811-4k`。
脚本核对设备、版本及原始和暂存模块的 SHA256；条件不符就停止。
运行前保存正在编辑的内容；这是第一次内核模块实测，离线检查不能排除异常重启。

## 执行

将测试 ZIP 解压，使文件位于：
`/sdcard/Download/17pm-sysctl-smoke/run-test.sh`。
在手机终端执行：

```sh
su -c 'sh /sdcard/Download/17pm-sysctl-smoke/run-test.sh'
```

脚本从下载目录读取模块，暂存到私有 `/data/local/tmp` 目录，临时加载，
读取 `/proc/sys/net/wonder/wonder_enable` 并要求值为 0。
退出处理会尝试卸载本次加载的模块，并核对模块及节点已消失。
不会写入开关或将它设为 1，不加载 provider、probe、Wonder 或 WLAN。
不修改 SELinux、不强制加载，也不安装 KernelSU 模块。
如果节点或模块原先就存在，脚本拒绝测试，不卸载原有模块。

正常完成时显示 `PASS_SYSCTL_LOAD_READ_UNLOAD`。
Download 中会生成 `17pm-sysctl-result-日期时间-PID.tar.gz`，包含版本、
步骤结果和经过关键词筛选的内核日志，不包含模块二进制。
上传这份结果包后，再决定下一阶段测试。

如果卸载失败，脚本将结果标为失败并提示重启清除临时模块。
若测试导致重启，不要自动重试，应先反馈重启情况。
PASS 只代表最小 sysctl 模块完成加载、读取和卸载，不代表 AWDL 或 AirDrop 可用。

## 维护

源码入口为 `tools/device/popsicle-sysctl-smoke.sh`。
`python3 tests/test_popsicle_sysctl_smoke.py` 使用模拟模块命令核对成功路径、
版本/校验失败、已有节点、加载失败、异常节点值和卸载失败；不会调用真正的 insmod。
