# 小米 17：以 MiShare 为入口的接入路线

最终入口是 `com.miui.mishare.connectivity`，参考
[小米 15 XAirDrop 固定版本](https://github.com/Leekin2/XAirDrop/tree/eb1fe215c6473a8dbcc6edf6cf1e67d93f250f76)。

## 参考项目实际做了什么

| 层 | 参考实现 | 小米 17 的状态 |
| --- | --- | --- |
| MiShare 应用 | `patches/build.py` 修改 DEX；Bridge 做网络注册回退与 Wi-Fi 会话控制，并修正 BLE 广播 | 已验证相同 DEX 并适配首段 BLE 补丁；broker 与 Wi-Fi 策略尚未接入 |
| 系统服务 | `DomesticXOsComm`、`libxos`、VINTF 和权限，以及 root NetworkBroker | 尚未验证本机兼容性或运行 |
| 无线驱动 | 复用并适配 OPAirDrop 的 AWDL WLAN/Wonder 模块 | 本机仅通过 Wonder 绑定生命周期，实际 WLAN 收发仍未实现 |

参考项目明确没有使用 LSPosed。它对确切 APK 做 smali 修改，构建后以临时 bind mount
让应用进程加载补丁代码；不是把修改后的 APK 当正常签名更新包安装。
这条应用接入路线与下层驱动移植是不同工作，最终都需要完成。
仅绕过可用性检测或出现 Apple 入口，不代表有 AWDL 通道。

## MiShare 的确切匹配条件

参考版本 `module/apply-patches.sh` 只接受原始 APK SHA256：
`394203fc35714c4c5d4b4e0b6d17ecaab239f5562a79bcf0a449ca36316cfa44`。
版本号相同并不能证明 APK 相同，原始 APK 必须先核对。

参考补丁涉及 `AwdlServiceClient`、混淆后的 BLE advertiser/WifiConflictManager，
以及地区/设备检查。小米 17 国行不应直接照搬全套常量返回值或假定这些限制存在；
必须逐项分析原始方法，只修改本机实际需要的逻辑。
小米 15 Ultra 专用 MiIntentResolver 补丁也不能照搬到本机。

原始 APK 由用户从设备导出并私下提供，不提交到公开仓库。
拿到 APK 后先验证包名、版本、SHA256、DEX 类与目标方法，再制作 Linux/Actions 构建流程。
所有编译仍在 GitHub Actions，沿用工具缓存；本机签名与授权行为要单独验证。

## 对上一段生命周期草稿的处理

`reservation` 指预留网络 adapter，不是存储或闪存预留，也不是安装模块。
`opairshare` 是参考代码沿用的前缀，不表示把手机当作一加。
该 MONITOR adapter 创建/销毁草稿尚未推送主分支，已暂停并保留草稿。
它不是小米 15 项目的 MiShare 接入实现，不能作为应用层进展。

当前优先推进本机 MiShare APK 的分析与补丁适配。底层六组缺口保持记录，不能宣称已解决。

## 本机 APK 分析与第一段应用补丁

用户提供 APK 的 SHA256 为 `3ca8032f3c55d53e1912a44e42a17334ff739a064cf603e6cb9afb09d810905d`。
确认版本 `5.4.2_20260923_1315` / 50402，minSdk 26、targetSdk 36。
两个 DEX 与二进制 Manifest 和上游公开参考包完全一致，但整包、签名文件、资源表与部分文件不同。
因此 Actions 可以只从公开参考包编译 DEX；最终合成必须保留本机原包的所有非目标条目，不能替换成参考 APK。
[原始 APK 审计](research/popsicle-mishare-apk-audit.json)。

本轮只修改 `a.u0` 的 BLE 广播 payload：按上游实现补入偏移 10 的版本字节，
将联系人哈希从偏移 4 移到偏移 11，保留最多 8 字节限制和 manufacturer ID 0x004c。
未修改地区、设备白名单、可用性检查、系统服务检测或分享面板。
国行路径原已放行，不能将 TapShare 的地区逻辑当作所有 AirDrop 功能都需解除的限制。

网络注册回退和 Wi-Fi 全频段断开策略暂未移植：需先确认本机权限/实际错误与无线共存行为，
不能把小米 15 的限制直接推广到小米 17。原生 NetworkAgent 与 Wi-Fi 管理逻辑保持不变。

`tools/mishare/ble_patch.py` 接受固定输入指纹，锚点或寄存器语义不符时停止；
只允许一个 smali 类变化。Actions 编译后重新反汇编真实输出，确认两处补丁确实进入 DEX。
Apktool 3.0.3 和公开参考包均按 SHA256 校验并缓存。
构建流程为 `.github/workflows/mishare-patch.yml`，不会重新触发完整内核构建。

本轮只生成 DEX 补丁与检查报告，没有可安装模块或自动挂载脚本。
即使 DEX 编译通过，修改后的 APK 也不能作为保留小米原签名的普通更新包安装。
未提供 APK 安装、证书替换或签名校验绕过功能；原厂 XOS 服务与 AWDL 后端依然需要完成。

补丁逻辑参考 Leekin2/XAirDrop 固定提交 `eb1fe215c6473a8dbcc6edf6cf1e67d93f250f76`
的 `patches/build.py`，本目录衍生脚本采用 GPL-3.0-only，完整许可见 `LICENSES/GPL-3.0-only.txt`。

## 编译结果与全类复核

[Actions 40296410028](https://github.com/xxz3312/XAirDrop-17/actions/runs/40296410028)
已完成 DEX 编译与反汇编验证，工具与参考包已在编译前缓存。
下载后独立核对产物摘要，并用用户原 APK 进行分析合入，所有非目标 ZIP 条目字节不变。

编译器省略了 18 个非目标类中冗余的静态 false/0/null 字段编码；
不能宣称所有非目标类的反汇编文本完全相同。现已加入严格的全类比对，
只忽略空行及这些类型匹配的默认静态字段编码，不归一化任何方法指令、非零值或实例字段。
在此范围之外，所有编译后类都与预期补丁源码一致。
[Actions 40297139875](https://github.com/xxz3312/XAirDrop-17/actions/runs/40297139875)
已通过这项必需的全类检查和 6 项 Python 补丁回归；工具及参考包缓存命中。

尚无设备运行结论；分析用 APK 没有签名和 ZIP 对齐认证，不提供为安装包或挂载测试包。
下一步需确认 MiShare 的 NETWORK_FACTORY 实际授权及 XOS 服务状态，不能根据 Manifest 声明推断已授予权限。

设备下一步只需进行只读检查，贴回以下输出以决定是否需要 root 网络代理：

```sh
su -c '
dumpsys package com.miui.mishare.connectivity | grep "NETWORK_FACTORY"
service check com.domestic.xoscomm.IDomesticXOsComm/default
'
```

仅出现 requested permissions 条目不代表已授权；需要结合 granted 状态判断。

## XOS 依赖适配审计

用户设备输出已确认 `NETWORK_FACTORY: granted=true`，XOS 服务 `not found`。
保留 MiShare 原生 NetworkAgent 注册；暂不加入 root broker。如果后续出现实际注册错误再分析。

对参考发布资产 `XAirDrop-1.0.zip` 做了纯静态检查，固定整包及四个 ELF 的 SHA256，
见 `tools/xos/profile.json` 和 [XOS 报告](research/popsicle-xos-reference-audit.json)。
发布标签可被重建，固定源码提交不能代替发布资产指纹；这些二进制的原厂固件出处未独立验证。

四个文件为 `DomesticXOsComm`、`com.domestic.xoscomm-V1-ndk.so`、`libxos.so`、`libev.so`。
它们都是 AArch64 ELF。服务通过 dlopen 加载 libxos，而非通过 DT_NEEDED 直接依赖它。
四者还需要设备提供 11 个外部库：libbase、libbinder_ndk、libc++、libc、libcutils、
libdl、liblog、libm、libnl、libpcap、libutils（后缀均为 .so）。
文件存在不等于 ABI 匹配，仍需核对符号版本、传递依赖和 linker namespace。

本机 MiShare 的 Binder 描述符及 startDomestXOsComm/stopDomestXOsComm/getStatus 名称
与参考 NDK 库相符；本机调用事务号为 1/2/3。尚未完整验证原生事务编码或 Binder 运行兼容性，
不能据此宣称服务可用。参考还增加 VINTF AIDL 声明，手工运行服务并通过策略放行。
本机 SELinux 域与现有 service_contexts 必须先采集，不能直接照搬上游广泛域授权。

参考发布包的 libxos 在 0x177f0/0x17a18 已是 `mov w19, wzr`，
0x177f4/0x17a1c 已是无条件成功分支：上游聚合配置错误绕过已存在于资产中。
这只是掩盖返回错误，不能证明 SET_FEATURES 被 Wonder 或 WLAN/固件实现。
本项目不会在本轮应用该补丁、分发该库或开启系统可用性开关。

`tools/xos/audit_reference.py` 使用 readelf 把参考二进制当作数据检查，完全不执行它们。
独立 Actions `.github/workflows/xos-audit.yml` 缓存已验证的参考资产，输出报告和只读采集脚本。
不触发内核或 DEX 编译，也不更改原有启动模块。

设备运行 `tools/device/popsicle-xos-audit.sh`（root）后，在 Download 生成报告。
脚本只读取设备信息、MiShare 权限/进程域、服务配置和 linker 配置，并复制所需库的候选路径；
不会加载模块、挂载、改 SELinux/VINTF、运行参考程序或切换 Wi-Fi。
报告用于后续离线符号与依赖比对，不应提交公开仓库。
底层无线 backend init 当前仍拒绝运行；即使完成服务依赖核对，完整 AirDrop 也未实现。


## 2026-10-26 设备库比对结果

用户上传的 XOS 报告 SHA256 为
`354f64e21587e09e9d4b5831dac51a0d7bf03031e44bf286bfea18e7c667d38e`。
设备为 OS4.0.5.0.XPBCNXM / API 37 / 4 KiB，SELinux Enforcing。
NETWORK_FACTORY 已授予，XOS 服务、xos0、Wonder PHY 和 wonder_enable 均不存在。

新增 `tools/xos/compare_device.py`，对参考 ELF 强引用与已采集 /system/lib64 导出逐项比较，
保留符号版本，支持 Android readelf 的 IFUNC（`<OS specific>: 10`）输出。
不使用 vendor/product 库填补系统符号，不把弱引用缺失误报为必需符号缺失。
4 项回归覆盖版本、默认版本、IFUNC、可见性与弱引用处理。

四个参考文件的强引用计数分别为 61、60、115、39（逐文件计数，有重复），
全部在候选作用域中找到版本匹配的导出。仅代表候选符号覆盖，不是实际 linker 加载、
符号选择顺序或完整原生 ABI 认证。
依赖递归核对发现还未采集 `libbinder.so`、`libvndksupport.so`、`ld-android.so`。
因此状态为 `REFERENCE_IMPORT_CANDIDATES_COVERED_CLOSURE_INCOMPLETE`，
见 [设备静态比对报告](research/popsicle-xos-device-audit.json)。

采集脚本已补充传递依赖常见库、bootstrap 路径、链接器、root 进程域和当前 APK 摘要，
用于下一轮补齐依赖链。当前没有启动 XOS、应用 SELinux 规则或启用 AirDrop。
完整 Manifest 解码与设备元数据均为 minSdk 26；先前无资源解码工作目录推断的 27
不能作为原 APK 的 minSdk，现已更正审计记录。DEX 输入指纹和非目标 APK 条目未改变。


## 补充报告与设备链接器依赖检查

第二轮设备报告 SHA256：
`ca069ddeada9453467e5f781a2b02d48b1d717e764b416dcfc8adb189332f540`。
已获得 libbinder、libvndksupport 和以 ld-android.so 为 SONAME 的真实 linker64。
当前运行 root 域为 `u:r:ksu:s0`；当前安装 APK 摘要与提供的原始 APK 完全相同。
四个参考 ELF 的强引用符号仍全部在候选依赖作用域中覆盖。
范围现在限于可达的 DT_NEEDED 链，避免不相关的已采集库提供假匹配。
传递依赖只剩未采集的 libapexsupport.so，libbinder 对 AApexSupport_loadLibrary
的引用因此尚未覆盖。这是采集缺口，不是设备缺库的结论。

符号解析现在拒绝跨行匹配空的 UND 条目，5 项回归包含该场景。
之前的解析可把下一行的序号当符号，或漏掉第一项导入；修正后已重新计算报告。
没有在 Android 设备上执行任何参考程序或修改系统状态。

新增 `tools/device/popsicle-xos-linker-audit.sh`：

- 只接受已核对的 popsicle / OS4.0.5.0.XPBCNXM / linker64 指纹。
- 用户自行下载上游 XAirDrop-1.0.zip；脚本校验整包与四个 ELF，项目不重新分发这些二进制。
- 将四个文件临时放在 /data/local/tmp 私有目录，权限 0400；清除继承的 LD_PRELOAD 等变量。
- 仅调用系统 linker64 --list，分别列出服务和 libxos 的实际依赖路径，15 秒超时，无执行回退。
- 不注册 Binder、不改 VINTF/SELinux、不加载模块、不启用 wonder_enable、不修改 MiShare 或 Wi-Fi。
- 采集尚缺的 libapexsupport，记录检查前后服务/网卡/Wonder 状态。完成后移除四个参考 ELF。
- 输出 PASS_DEPENDENCY_PATHS_ONLY 只代表两个 --list 成功且所观察状态相同；不是符号重定位或服务启动通过。

AOSP 的 --list 会设置 g_is_ldd，跳过目标构造函数、目标入口和符号重定位。
参考实现：[入口与模式](https://android.googlesource.com/platform/bionic/+/2fbbc253f6886524a4a6e56ad763100d05b6ddcd/linker/linker_main.cpp)、
[构造函数跳过](https://android.googlesource.com/platform/bionic/+/1c33c4a26333258275cc6724a692d4ca7adc60e4/linker/linker_soinfo.cpp)、
[重定位跳过](https://android.googlesource.com/platform/bionic/+/d512580522ab8024264b08b19fc2c1951aefbc5d/linker/linker_relocate.cpp)。
已采集本机 linker64 含 --list 支持；本机运行结果仍待用户执行并回传。
原生源码版本与本机二进制未建立逐指令一致性证明，这不是完整运行认证。

用法（不安装参考 ZIP）：

```sh
su -c 'sh /sdcard/Download/popsicle-xos-linker-audit.sh /sdcard/Download/XAirDrop-reference-1.0.zip'
```

结果为 Download/17pm-xos-linker-*.tar.gz。该报告不包含四个参考 ELF。
依赖路径检查完成后，仍须验证 Binder/VINTF/SELinux，底层 AWDL 后端缺口继续单独推进。
