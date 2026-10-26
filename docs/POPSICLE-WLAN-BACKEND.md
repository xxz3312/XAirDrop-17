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

## 主机模式层第一段实现

`0004-mishare-passthru-host-modes.patch` 面向固定的 Xiaomi popsicle 源码，
没有恢复此前 MONITOR reservation 草稿，也没有另建 OP/OShare 模块。
本段增加 QDF_PASSTHRU_MODE（17）、wlan_op_mode_passthru（7）、模式名称与
QDF 到 CDP 的转换。原 QDF 0–16、CDP 0–6 数值保持，QDF_MAX_NO_OF_MODE 从 17 变为 18。
上限变化会影响以它定义的数组，不能仅凭原枚举值不变宣称完整 ABI 不变。

专用 MLME ops 和固件类型尚未实现，本轮明确拒绝新模式的 MLME 注册和固件类型转换，
转换失败时 type/subtype 都为 0，不能落入 STA ops 或发送未经验证的 0x9。
HDD open 也提前拒绝该模式，避免进入已有 unknown-mode QDF_ASSERT。
未增加接口创建、操作表注册、开机动作、传输、频道操作或固件命令。
此段是源码移植基础层，不是可工作的无线后端。

`passthru_mode_fixture.py` 在 Actions 中提取固定原始源码和补丁后源码中的真实 C：
模式名、QDF/CDP 转换、MLME ops 选择和固件类型转换。只模拟对象访问器及日志，
逐一执行 17 种既有 QDF 模式并比较前后结果；同时核对原 7 种 DP 模式数值，
断言新模式转换及两条拒绝路径。使用真实 QDF_STATUS 和类型宏，不改写生产函数。
主机夹具不验证真实对象管理、并发、策略数组或固件。

完整 WLAN 仍需走现有 Actions 编译、严格链接、依赖/重复导出检查及选定布局检查。
源码缺口报告现在有两组模式标识接上，但其余 HDD、合同、构建入口及固件类型仍缺失，
不能将缺口计数降低当成初始化、收发或硬件能力验证。
本轮不提供替换原厂 WLAN 的安装步骤；后续继续接口生命周期和真实后端接线。

### 与当前原厂模式表的交叉核对

独立解析原厂 ELF 的 AArch64 ADRP/ADD 重定位目标和字符串表项后，确认原厂
`qdf_opmode_str` 的第 17 项已经是 PASSTHRU；对应 `wlan_util_vdev_get_cdp_txrx_opmode`
数据表也将 17 映射到 7。本轮补丁的新增编号与当前原厂这两张表一致，
不只是沿用参考项目的编号。[原厂表记录](research/popsicle-stock-passthru-modes.json)
保存模块摘要、函数位置、表所在节和偏移以及全部表项。

这同时说明：公开源码缺少模式定义，与原厂二进制中已有模式表是两件事。
原厂表项存在和此前两个空实现可以同时成立；不能由表项存在认定后端或固件已启用。

进一步反汇编原厂 `vdevmgr_mlme_ext_hdl_create`：0x16e7d8 比较 mode=17，
0x16e7e0 将 9 写入 w8，0x16e83c 存储该字节，0x16e88c 的调用重定位指向
`vdev_mgr_create_send`。结合公开源码的同名创建路径，这是原厂主机侧
17→类型9 的请求构造证据；不能当作固件已接受该请求的证据。
本轮仍保留新模式创建拒绝路径，没有因此提前启用 WMI 或无线。

### 本轮 Actions 验证完成

运行 40324761015（源码 fc94047e0021e5fdf4ccaee2f14fb826044f083d）全部通过。
已下载并核对 Artifact SHA256，再独立重新生成补丁前/后 C 夹具源码，摘要均与
Actions 报告一致。17 项既有模式名称/转换的结果也与原厂表交叉匹配。
新模式的转换、拒绝注册并清空旧 ops、类型输出清零均通过 C 断言。

完整 WLAN 编译、严格链接及 CNSS 名称覆盖检查通过；未解析 WLAN 依赖为 0。
573 条导入版本记录无不匹配，离线状态为 RECORDED_LOADER_CHECKS_MATCH_ONLY，
这不独立认证声明或完整 ABI。module/net_device/wiphy/wireless_dev/sk_buff/
cfg80211_chan_def/ieee80211_channel 的选定直接布局核对通过。
工具链及 bindgen 缓存均命中，没有改写 vermagic、CRC 或放宽 modpost。
详细结果见 [本轮构建记录](research/popsicle-passthru-host-mode-build-pass.json)。

本轮模式层基础实现完成。仍未安装候选 WLAN，未调用固件或测试收发。
诊断 Artifact 包含两份带调试信息的对象/模块归档，不是 KernelSU 模块或精简安装包。
下一段是 HDD 接口生命周期和专用 Wonder 操作表；固件类型请求与收发需要独立实现及验证。

## HDD 主机接口生命周期：尚无运行时调用者

新增 `kernel/popsicle-hdd/wlan_hdd_mishare_host.c/.h`，使用 QDF_PASSTHRU_MODE=17，
不是此前暂停的 QDF_MONITOR_MODE reservation 草稿，也没有另建模块。
代码编入现有 WLAN；普通 `hdd_open_adapter` 的原型和新模式拒绝行为保留，
专用内部工厂才可创建 `misharewt%d`。

- create/destroy 均要求调用者持有 RTNL 和独占父 psoc transition，owner 访问由同一调用者串行化。
  函数内只断言前置条件，不在持 RTNL 时再等待父锁，避免引入倒序等待。
- 校验上下文、单播 MAC、已有 owner 与 PASSTHRU adapter；分配 owner、vdev sync、
  真实 HDD adapter，再注册 sync。每一步失败按逆序释放，失败不发布 owner。
- 接口只处于 DOWN 状态，ndo_open 返回 EOPNOTSUPP；没有 ndo_start_xmit。
  Linux host 的 radiotap/wdev framing 使用 MONITOR 类型，QDF device_mode 仍为 PASSTHRU，
  没有创建 QDF_MONITOR_MODE adapter 或向固件请求 monitor vdev。
- cfg80211 类型切换和普通删除路径提前拒绝此模式，删除拒绝发生在 sync 注销前，
  owner 专用销毁走 HDD close；避免用户态删除让 owner 保留已释放指针。
- 销毁拒绝 running、DEVICE_IFACE_OPENED、SME_SESSION_OPENED 状态，保留 owner。
  注销 sync、等候操作退出、关闭 adapter、销毁 sync、释放 owner；关闭后不再访问 adapter。
  sync 注册关系异常则返回 EIO 并保留 owner 供诊断，不释放归属不明的资源。
- 专用工厂注册 netdev 后发生失败时，先复制 MAC，再调用可能释放 adapter/netdev 的清理，
  最后用保存的 MAC 回收 DP interface，并直接返回，避免读取已释放 adapter 或重复释放 netdev。

它没有 start/channel/TX/RX/WMI 调用，没有开机入口、导出符号或运行时调用者，
也尚未连接 Wonder 的 init/deinit；host create 成功只表示 DOWN 主机对象分配成功。
调用者必须在 HDD context 销毁之前回收 owner。实际注册操作表和卸载/恢复接线还未完成，
因此这一段不能装到手机上声称可运行，也不能让 Wonder init 返回成功。

Actions 使用同一份生产 C 和提取的工厂/错误清理片段做 ASan/UBSan 失败注入：
owner/sync/adapter 分配失败、无效上下文、重复 owner、活动接口拒绝、同步对象不匹配、
注销/排空/关闭/销毁顺序、重复销毁及工厂失败后的释放顺序。底层 HDD/同步由夹具模拟，
不能替代内核并发、cfg80211 注册或驱动卸载实测。
完整 WLAN 对象和最终 .ko 都必须实际包含三个新函数，避免源码存在但未编入。
工具链和 bindgen 沿用编译前缓存；后续仍跑严格链接、依赖与选定布局检查。

### 原生 Wonder 操作表注册/撤销接线

新增 `wlan_hdd_mishare_backend.c/.h`。HDD probe 全部成功后尝试可选表注册，
SoC remove 在销毁 HDD context 前同步撤销；注册失败只记录附加功能失败，
普通 WLAN 的已完成启动不被改成失败。重复注册同 owner 幂等，其他 owner 返回 busy，
错误 owner 或重复撤销不清除其他注册。

`mishare_wonder_attach` 参数默认 false、权限 0444。默认不注册、不创建接口、不调用固件。
即使将来受限实测时启用该参数，本阶段也只有强类型操作表绑定：init 清空输出 handle 并
返回 EOPNOTSUPP，频道/过滤/速率操作返回 EOPNOTSUPP，capabilities 全零，
不会把 DOWN host helper 的成功冒充无线初始化。host helper 尚未由无线 init 调用。

表头直接复制已验证 provider 的 wondertap.h，夹具也使用同一原始头文件。
注册/撤销可能在持 owner mutex 时同步触发表查询，因此所有回调不获取该 mutex、
不解引用 HDD context，也不启动硬件，避免组件回调重入形成递归锁。
模拟 provider 会在 bind/unbind 时实际调用 capabilities/init 来验证这一点。

WLAN 使用强导入 `opairshare_set_wonder_priv_data`，不覆盖原厂 CNSS 导出、
不通过动态符号查找跳过依赖验证。候选 WLAN 因此新增 private provider 模块依赖，
即使默认关闭参数也需要匹配 provider 存在；这也是当前不能直接替换手机原厂 WLAN 的原因之一。
provider 的实际生成 Module.symvers 与原厂供应者记录合并后交给严格 modpost，
最终 .ko 必须记录 opairshare_wonder_provider 依赖。静态模块依赖保证 provider 在
WLAN 存活期间不能先卸载，满足其 NULL 清除操作同步且成功的约定。

测试覆盖默认关闭、注册失败回滚、重复/冲突 owner、错误 owner 撤销、回调重入、
零能力、init 不发布 handle、不支持的控制操作、重复撤销和重新注册。
这仍是表归属与生命周期接线，尚未验证真实内核组件并发、恢复过程或无线功能。
完整对象和最终模块现在都需包含三个 host helper/工厂函数及两个表注册/撤销函数。

### 主机生命周期与表接线构建验证通过

运行 40333754071，源码 1abe45bb2cf677b93bebe1fd5744266441af0867，全部步骤通过。
工具链及 bindgen 均命中缓存。模式对照、生产 host C 的 ASan/UBSan 失败注入、
生产 typed table 的模拟组件重入测试全部通过。已下载并校验 19,112 字节的独立
validation artifact，重新生成两组 C 测试片段摘要并核对生产文件摘要，与报告一致。
两个 Wonder API 头文件逐字节一致。

完整 WLAN 对象和 .ko 都包含三个 host 工厂/生命周期函数及两个表注册/撤销函数。
最终模块实际依赖 opairshare_wonder_provider；WLAN 未解析导入为 0，
574 条导入版本记录无不匹配，七项选定直接布局检查通过。
详细状态和限制见 [本轮验证记录](research/popsicle-mishare-host-lifecycle-build-pass.json)。

该阶段代码和离线构建验证完成。默认表绑定仍关闭，主机 helper 不由无线 init 调用，
init/频道/速率/过滤操作仍返回不支持，未提供手机安装或启用步骤。
下一段是 MLME/vdev 初始化与完成/失败事件、固件类型 9 请求及 RX/TX 接线，
需要另行处理真正启动后对象的停止、回收和恢复；不能直接撤掉保护返回成功。
