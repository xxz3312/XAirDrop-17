# 第三阶段：Wonder component 绑定生命周期

## 当前状态：实机绑定、解绑和重新绑定通过

目标设备已返回 `PASS_MASTER_BIND_UNBIND_REBIND`，退出码为 0。
新增日志按顺序确认初次绑定 → 注销操作表 → 重新绑定 → 最终注销和硬件卸载。
全部本次模块所有权标志为 0，前后网络接口名称完全一致；原有 mac80211 未卸载。
[实机通过记录](research/popsicle-master-device-pass.json)。本阶段无需重复运行。

这只验证虚拟硬件注册及 component 生命周期；probe 无线 init 仍为不支持。
没有验证 WLAN 后端、接口启动、TX/RX、AWDL、XOS 或 AirDrop。

## 产物与既有失败记录

[Actions 40284559893](https://github.com/xxz3312/XAirDrop-17/actions/runs/40284559893)
已完成原生编译、19 个 allocator 回调偏移断言、严格链接、依赖/重复导出检查、
选定布局与记录的原厂加载规则检查。下载产物后再次直接核对实际 ELF：
`add/remove/change_chanctx` 分别位于 `0x250/0x258/0x260`，
必要回调均存在，assign/unassign 为空；与 Actions 生成的检查报告完全一致。
[修订产物报告](research/popsicle-master-rebuild-allocator-pass.json)。

原实机失败候选的 `add_chanctx` 位于 `0x240`。第一轮修订 40281240881 的设置
误放在被 Kbuild 覆盖的 Makefile 中，产物仍是旧模块，已拒绝分发。
当前修订使用真正的 Kbuild，并强制检查链接后的实际回调重定位。
[问题与旧构建记录](research/popsicle-mac80211-allocator-audit.json)、
[首次实机失败记录](research/popsicle-master-device-failure.json) 均保留。

旧测试包作废。以下说明只适用于新产物；仅已完成上述受限实机测试，不代表完整 mac80211 ABI 或无线收发验证。
原生源码提交 `36f5a9cba7a13ca16639bb14fdbabab1e63c8ff3`。
本包使用 Actions 原始字节，不本地重新编译、strip 或改写版本/CRC。

| 模块 | SHA256 |
| --- | --- |
| wonder.ko | `967d50c09eb217ff4dacb47e505ad5c8ae11fae454c7afc28d0e72f1bf333755` |
| opairshare_wonder_provider.ko | `8b1c55b4d98d2867209671e47b4e2b676e64d19553f7e2bf611201dadfc4ab6a` |
| opairshare_route_b_probe.ko | `158e250cbef5d64f906758bdb2fea9ca755a9c4aa9ca6c2748ea8e5171ef8ade` |

仅用于 popsicle / OS4.0.5.0.XPBCNXM /
`6.12.69-android16-6-g43b5ab7e247d-abogki558343811-4k`。
测试前保存正在编辑的内容。

## 运行

本 ZIP 是终端测试包。先删除旧的 `17pm-master-smoke` 解压目录，再解压新包到 Download，使脚本路径为
`/sdcard/Download/17pm-master-smoke/run-test.sh`，然后执行：

```sh
su -c 'sh /sdcard/Download/17pm-master-smoke/run-test.sh'
```

脚本要求原厂 WLAN/cfg80211 已加载，没有已有 Wonder 模块、设备、PHY 或可用性节点。
每份候选模块在源文件与暂存文件两处核对 SHA256。

Wonder 依赖原厂 `mac80211`。无论它是否已加载，脚本都会先从手机
原有模块目录核对 SHA256 为
`01b40a32346277f30b807d31c4acd7011e18c38bdff594282f5e835d40f40dec`
的文件；只在尚未加载时临时加载并记录所有权。
随后核对 `/sys/module/mac80211/notes/.note.gnu.build-id` 的完整 note 哈希，
对应 Build ID `6086b536b2d52fe7bcd16d12f44f89486e3c5f95`。
已加载模块身份不符或无法核对时，在加载实验模块前停止；不卸载已有模块。
测试包不分发、替换或修改原厂模块。
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
