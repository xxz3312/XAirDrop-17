# 第二阶段：私有 provider/probe 生命周期

前置条件：第一阶段 `wonder_sysctl` 加载、默认值 0 和卸载已实测通过。
本阶段验证私有桥接模块与探针的加载、注册、拒绝竞争注册、注销和卸载。
尚不验证 Wonder 主模块、无线回调、WLAN、AWDL、XOS 服务或 AirDrop。

本阶段现已在目标设备实测通过：日志确认版本 5 的探针重复/竞争注册检查通过，
退出时清除了操作表，provider/probe 均卸载，退出码为 0。
脱敏记录见 [第二阶段实机结果](research/popsicle-provider-device-pass.json)。
下一阶段先修复 Wonder 主模块的 probe 失败清理，再构建验证，尚未提供主模块测试包。

两份模块均来自成功运行
[40229703474](https://github.com/xxz3312/XAirDrop-17/actions/runs/40229703474)，
已校验 Artifact 和各模块 SHA256；没有本地编译或修改 ELF。

| 模块 | SHA256 |
| --- | --- |
| opairshare_wonder_provider.ko | `8b1c55b4d98d2867209671e47b4e2b676e64d19553f7e2bf611201dadfc4ab6a` |
| opairshare_route_b_probe.ko | `158e250cbef5d64f906758bdb2fea9ca755a9c4aa9ca6c2748ea8e5171ef8ade` |

仅用于 popsicle / OS4.0.5.0.XPBCNXM /
`6.12.69-android16-6-g43b5ab7e247d-abogki558343811-4k`。
这是首次测试这两个内核模块，运行前保存正在编辑的内容。

## 执行

解压终端测试 ZIP，使脚本位于：
`/sdcard/Download/17pm-provider-smoke/run-test.sh`。

```sh
su -c 'sh /sdcard/Download/17pm-provider-smoke/run-test.sh'
```

脚本要求原厂 WLAN 模块仍在，且没有已有 Wonder 节点、Wonder 主模块、
私有测试模块或同名 platform 设备；不满足时不加载测试模块。
验证文件校验值后临时加载 provider，再加载 probe。
probe 的初始化会真实调用私有注册接口，核对同一对象重复注册及另一对象竞争注册。
该探针未提供可工作的无线实现，不应被当作 AirDrop 后端。

脚本退出时先卸载 probe 以清除回调，再卸载 provider 以移除平台设备。
如果 probe 卸载失败，保留其依赖的 provider，不强制卸载，并报告失败。
不会修改原厂 CNSS、替换 WLAN、加载 Wonder 主模块、写入开关、禁用 SELinux、
强制加载、安装 Root 模块或创建开机启动项。

正常结果为 `PASS_PROVIDER_PROBE_REGISTER_UNREGISTER`。
上传 Download 中生成的 `17pm-provider-result-日期时间-PID.tar.gz`。
这份结果包不包含模块二进制，只记录必要版本、测试步骤和筛选日志。
若设备重启则停止重试并反馈重启情况；卸载失败时保存报告后重启清除临时模块。

脚本源码：`tools/device/popsicle-provider-smoke.sh`。
可用 `python3 tests/test_popsicle_provider_smoke.py` 运行仅使用模拟模块工具的
卸载顺序、注册失败清理、卸载失败保留依赖及已有设备保护检查。
