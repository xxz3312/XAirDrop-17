# 第四阶段：小米 17 Pro Max 真实 WLAN 后端

第三阶段已验证 Wonder/mac80211 与诊断 provider/probe 的绑定生命周期。
它没有调用探针的无线 init，也没有创建 netdev；该结果不能证明收发路径已存在。

## 已核对的源码

MiCode WLAN 固定提交 `36df473046706a5259942e1bf7222108dbbb860f`，
版本 5.2.1.137C；原机驱动 5.2.1.146N。具体文件字节哈希及检查结果见
[源码缺口报告](research/popsicle-wlan-backend-gaps.json)。

| 层 | 当前源码 | 移植工作 |
| --- | --- | --- |
| HDD 后端与构建 | 没有 `wlan_hdd_wondertap.c/.h` 和对应 Kbuild 条目 | 适配真实 Wonder ops，接入当前 HDD 生命周期，核对返回值和失败回滚 |
| 主机工作模式 | 没有 `QDF_PASSTHRU_MODE` | 核对所有模式转换、策略数组、并发与 vdev 创建/销毁分支；保留已有枚举值 |
| 数据面模式 | 没有 `wlan_op_mode_passthru` | 接通发送描述符、完成通知和 RX 路由；仅增加枚举不能实现收发 |
| 固件接口 | 没有 `WMI_VDEV_TYPE_WIFI_PASSTHRU` 定义 | 需要目标固件支持证据，不能把参考项目的 0x9 当成本机支持结论 |
| 现有 monitor | 有 open/stop/stats，net_device_ops 没有 ndo_start_xmit | 可研究接收路径；不能直接作为原始数据帧发送接口 |
| 管理帧发送 | 有 `wlan_hdd_mgmt_tx` | 与 monitor RX 是不同路径，不能据此认定支持 AWDL 数据传输 |

以上是源码标识及结构检查，不是函数实现完整性、可达性、ABI 或固件认证。
开源中缺少某个名称，也不能证明手机硬件一定不支持该功能。

## 调用链入口与顺序

1. **HDD 生命周期**：`wlan_hdd_driver_ops.c` 的 SoC probe/remove；还需覆盖恢复与电源路径。
   注册真实操作表时处理失败；先撤销操作表并等候在途调用退出，再销毁 adapter/context。
   不能把上一阶段 probe 的 `-EOPNOTSUPP` 改为成功来充当实现。
2. **接口生命周期**：`wlan_hdd_main.c` 的 `hdd_open_adapter`、`hdd_start_adapter`、
   `hdd_stop_adapter`、`hdd_close_adapter`。当前声明含 `hdd_adapter_create_param` 和
   `rtnl_held`；不能照搬旧平台调用参数。必须理清 RTNL、psoc/vdev sync 与对象引用的持有者。
3. **频道与接收**：`wlan_hdd_set_mon_chan`、`wlan_hdd_rx_monitor.c` 中
   `hdd_enable_monitor_mode`/`hdd_disable_monitor_mode`。需继续追到 DP monitor ring、
   radiotap/802.11 元数据及 skb 所有权，退出时等待异步 RX 结束。
4. **发送与完成通知**：`wlan_hdd_p2p.c` 的 `wlan_hdd_mgmt_tx` 仅是管理帧入口。
   真实数据发送必须另外核对 DP BE TX、peer/vdev 引用、发送完成、失败释放和频道切换同步。
5. **固件与共存**：最后确认创建该 vdev 类型、频道切换和并发能力的目标固件支持。
   没有证据时保持未验证，不能通过跳过策略、伪造成功或仅创建 xos0 来宣称可用。

仓库 `kernel/driver/wlan_hdd_wondertap.c` 包含原参考平台的多种诊断与管理帧路径，
不是当前 popsicle 源码的一部分。不能将整份文件复制进来并启用旧平台参数。
移植应分层提交；先完成 host 侧创建/撤销及错误路径，再进入收发和固件验证。

## 可重复的源码检查

```sh
python3 tools/kernel/popsicle_backend_audit.py \
  --wlan /path/to/pinned-wlan \
  --output /path/to/wlan-backend-gaps.json
```

脚本核对 Git 提交、实际工作文件哈希、原有调用入口、六组源代码接线和 monitor TX 条目。
即使所有标识存在，状态也只能是 `SOURCE_IDENTIFIERS_PRESENT_REVIEW_REQUIRED`。
`radio_usable` 保持未知，固件支持保持未验证。`--require-source-plumbing` 可将缺少接线
作为退出码 2，但不能用它认证收发；默认生成报告，供仍在移植的 baseline 构建使用。

Actions 在 setup 阶段自动产生 `reports/wlan-backend-gaps.json`，会包含已经应用的兼容补丁。
本次新增的是源码审核与持续报告，没有启用或实现无线后端，不提供新的实机测试包。
全部原生编译继续在 GitHub Actions 执行，沿用现有工具链缓存。

## MiShare Binder 通过后的固件输入核对

2026-10-26 20:01 的真实 MiShare main/:ui Binder 元数据测试均通过，结果见
[应用调用记录](research/popsicle-mishare-binder-device-pass.json)。
当前转向无线后端，暂停重复应用权限、服务注册及元数据测试。

固定公开源码的 `fw-api/fw/wmi_unified.h` 定义 WMI vdev 类型 0x1 到 0x8，
没有参考实现使用的 `WMI_VDEV_TYPE_WIFI_PASSTHRU`。QDF、DP、HDD 和 Kbuild
对应接线也仍缺失。这是公开源码现状，不代表当前手机固件一定不支持 0x9。
不能单独添加该数值、跳过错误或改成 MONITOR 就认定实现 PASSTHRU。
此前暂停的 MONITOR adapter reservation 草稿继续保留在 stash，未恢复、未部署。

新增 `popsicle-wlan-fw-audit.sh` 只读收集当前固件候选及已核对原厂 WLAN 文件：

- 固定 popsicle/OS4.0.5.0；只复制 SHA 匹配的原厂 qca_cld 模块。
- 在 vendor/odm 固件目录寻找 amss/qwlan/wlanmdsp 常见文件和分段，记录来源、
  解析路径、大小、SHA256；按内容去重，单文件最多 64 MiB、总计最多 128 MiB。
- 只读已有内核消息和公开模块信息；不读取 debugfs、原始分区、BDF/校准或 Wi-Fi 配置。
- 不加载驱动、不启动 XOS、不重启 Wi-Fi、不创建网卡、不发送固件命令。
- 文件候选不等于当前活动镜像；字符串命中或缺失均不直接认证 PASSTHRU 能力。

Actions `wlan-fw-audit.yml` 做脚本语法检查并提供工具 ZIP，不触发原生编译。
解压脚本到 Download 后执行：

```sh
su -c 'sh /sdcard/Download/popsicle-wlan-fw-audit.sh'
```

上传 `17pm-wlan-fw-*.tar.gz`。随后核对候选固件与驱动中的 vdev 类型转换、
相关命令处理证据，再决定原生 PASSTHRU 后端的接线与受限实测方案。
当前没有新的可刷无线模块，也未宣称后端初始化或收发通过。

## 20:26 固件输入到齐，原厂 PASSTHRU 名称对应空实现

采集报告 SHA256 `8b870e358cd522a43bef648d33311f962727cd681a51c60a1da62ad61d31cdac`。
已逐个校验复制文件摘要；SELinux 为 Enforcing，采集前后状态一致。
原厂 `qca_cld3_peach_v2.ko` SHA256 仍为
`202977cadf13b330a21838f3dd222cb0886eb0649d705937a778d7da69085f75`。
日志未提供实际加载固件路径，故以下仍是候选；按当前 Peach 驱动优先分析 Peach 镜像。

| 来源 | SHA256 | 固件版本标记 |
| --- | --- | --- |
| peach/amss20.bin | 8d0ac09be5489393ed23c19ace3ea9e44ceff5e29c4bb75ea3d22acf26d92e8f | WLAN.GNG.2.0-01294.3-QCAGNGSWPL_V2_TO_SILICONZ-1.121647.68.168475.4 |
| kiwi/amss.bin | c42e06f534c07ffdaec3b265ff1e38b312741e35eb5fb21b5ca77995fab8d688 | CI_WLAN.HMT.1.0-02352.5.1-QCAHMTSWPL_V1.0_V2.0_SILICON-2 |
| kiwi/amss20.bin | e16100daffd481a40d66476ec7e3e4f3c6cfd6ac48bbd1a033d58ebcbdca8756 | WLAN.HMT.2.0-03335-QCAHMTSWPL_V1.0_V2.0_SILICONZ-1 |

Peach 文件开头是 ARM ELF32，偏移 0x80000 处还有有效 QDSP6 ELF32（21 个 program
headers、无 section table）。另一个 0x44345e 处的 ELF 字样头部无效，不算第三个镜像。
扫描器校验头部、program table 和 segment 边界，不能仅查 magic。
没有符号表/节表，字符串检索未定位出可认证的 PASSTHRU 命令处理路径。
这不等于证明固件不支持 0x9；仍需专门的 DSP 命令分发分析或后续受限固件实测。

原厂模块符号表确有两个相关函数，已读取所在 .text 的真实字节并独立反汇编：

| 函数 | 字节 | 实际指令 |
| --- | --- | --- |
| hdd_sme_passthrough_mode_callback | c0035fd6 | ret |
| dp_tx_send_passthru | e00302aac0035fd6 | mov x0, x2; ret |

这两处函数体没有调用、数据拷贝或发送实现；不能因符号存在就把它们作为收发后端。
返回参数的含义仍需结合调用者/原型核对，不仅凭名称推断全局发送行为。
本结论也没有证明其他驱动路径或固件内部一定缺少 PASSTHRU 支持。

`tools/kernel/firmware_image_audit.py` 可离线重验容器结构、版本标记和原厂空实现字节。
[完整元数据记录](research/popsicle-wlan-firmware-device-audit.json) 包含文件摘要、来源、
各层 ELF、函数偏移和明确限制；不提交原厂固件/模块二进制。
夹具覆盖嵌套 DSP、无效内嵌 magic、截断头部/段及纯字符串不能认证能力。

采集脚本旧版把所有非 Peach 模块都标成 STOCK_MODULE_HASH_CHANGED，含义不准确。
Kiwi/WCN7750 是其他随系统提供的型号变体；现改为 OTHER_WLAN_VARIANT_NOT_SELECTED。
只有被选中的 Peach 模块不匹配才标 HASH_CHANGED。新增负例测试，原报告无需重跑。

已有输入足以继续主机侧源码移植，无需重复固件采集。驱动生命周期、模式转换与收发路径
需要真实实现；不能 hook 空函数、直接写模式数值或让 init 返回成功来替代。
当前没有新可刷驱动；原生编译仍通过现有缓存的 GitHub Actions 执行。
