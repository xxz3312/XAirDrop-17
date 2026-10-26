# 第三阶段：Wonder component 绑定生命周期

前两阶段已在目标设备验证最小 sysctl 加载/卸载和 provider/probe 注册/注销。
Wonder 的失败路径已修复，并由
[Actions 40274658306](https://github.com/xxz3312/XAirDrop-17/actions/runs/40274658306)
完成完整模块链接、依赖/重复导出检查、选定布局与原厂加载规则检查。
这些仍是离线检查，Wonder 主模块尚未在目标设备加载。

本测试使用该运行的 3 个原始 `.ko`，不本地重新编译、strip 或改写版本/CRC：

| 模块 | SHA256 |
| --- | --- |
| wonder.ko | `5270dab5e09c33c39f4b2a70f3ab766cb36cd072bb8464bbe152e8b79e0560a9` |
| opairshare_wonder_provider.ko | `8b1c55b4d98d2867209671e47b4e2b676e64d19553f7e2bf611201dadfc4ab6a` |
| opairshare_route_b_probe.ko | `158e250cbef5d64f906758bdb2fea9ca755a9c4aa9ca6c2748ea8e5171ef8ade` |

仅用于 popsicle / OS4.0.5.0.XPBCNXM /
`6.12.69-android16-6-g43b5ab7e247d-abogki558343811-4k`。
这是首次加载 Wonder 主模块，测试前保存正在编辑的内容。

## 运行

本 ZIP 是终端测试包。解压到 Download，使脚本路径为
`/sdcard/Download/17pm-master-smoke/run-test.sh`，然后执行：

```sh
su -c 'sh /sdcard/Download/17pm-master-smoke/run-test.sh'
```

脚本要求原厂 WLAN/cfg80211 已加载，没有已有 Wonder 模块、设备、PHY 或可用性节点。
每份候选模块在源文件与暂存文件两处核对 SHA256。

Wonder 依赖原厂 `mac80211`。如果它已加载，就不改变其原有状态；否则仅从手机
原有模块目录寻找 SHA256 为
`01b40a32346277f30b807d31c4acd7011e18c38bdff594282f5e835d40f40dec`
的文件，临时加载并记录所有权。测试包不分发、替换或修改原厂模块。
找不到相同文件或无法加载时停止，不强制加载或下载其他版本。

过程：加载 provider、probe、Wonder；检查平台驱动绑定、虚拟 PHY，
以及本次新增的 component 绑定日志；在主模块仍加载时卸载 probe，
检查操作表注销的新日志；重新加载 probe 并核对重新绑定的新日志。
旧日志不能充当本次绑定成功证据。

不执行 iw/ip、创建网络接口、启动接口、扫描、传输、改频道或开启互传入口。
Wonder 本身会注册一个临时虚拟 PHY；若发现网络接口名称变化，则中止测试并清理。
探针的无线 init 仍明确返回不支持，不是无线后端。

退出时按 Wonder → probe → provider → 本次加载的原厂 mac80211 的顺序卸载。
某层无法卸载时保留其依赖，不强制卸载，结果标为失败。
原来已加载的 mac80211 和原厂 WLAN 保持不动。

正常输出 `PASS_MASTER_BIND_UNBIND_REBIND`。
上传 Download 中的 `17pm-master-result-日期时间-PID.tar.gz`。
结果包仅含必要版本、阶段结果、筛选日志和前后接口名称，不含 `.ko`。
若发生重启，应停止重试并反馈重启情况；若临时模块无法卸载，保存报告后重启清除。
PASS 仅代表 component 绑定生命周期通过，未验证 WLAN 后端、固件、AWDL、XOS 或 AirDrop 收发。

源码：`tools/device/popsicle-master-smoke.sh`。
`python3 tests/test_popsicle_master_smoke.py` 用模拟 sysfs 和模块命令核对
绑定、解绑、重新绑定、清理顺序、保留既有依赖、绑定失败、重新绑定失败、
卸载失败及意外接口出现的处理，不会调用真实的 insmod。
