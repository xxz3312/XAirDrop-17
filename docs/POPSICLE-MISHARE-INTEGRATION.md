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


### 链接器预检摘要修正

首版依赖检查脚本误把 /system/lib64/ld-android.so 的摘要填入 /system/bin/linker64
校验，设备输出 Unexpected linker 并在提取参考 ELF 或运行 --list 之前停止。
已根据用户第二轮原始报告重新核对两个 linker64 路径：

- /system/bin/linker64 与 /apex/com.android.runtime/bin/linker64：
  `b6dd216b7a775b8f04c825cada286bfe7ddaeecf2c0c10e617287118965abc00`。
- /system/lib64/ld-android.so 是独立文件：
  `e6d7b18d770a8159e0670ca81e5357d10c47a56052db2e7d964c4da16498d305`。

二者有相同相关 SONAME 不能推导文件摘要相同。
新增 tools/xos/device-profile.json 区分可执行链接器与系统 stub，回归检查脚本的
可执行链接器门限与该设备证据一致；摘要不符时打印预期与实际值。
未放宽校验或修改设备，原参考 ZIP 无需重下载。设备 --list 结果仍待回传。


## 依赖路径实机通过与下一步加载探针

2026-10-26 18:05（设备报告时间）结果为 PASS_DEPENDENCY_PATHS_ONLY：
服务与 libxos 的 --list 均退出 0，检查前后网卡名称、服务存在性及 Wonder 状态相同。
报告 SHA256 为 `319f83559599dbad3b93e2301d24dfcd644e94da14a43cc1133763b30e95c4bc`。
libapexsupport 实际解析到 /system/lib64/libapexsupport.so，其摘要为
`63a33ac9e7455b0834131a6786c81f4ec7a9f0d0432121e19ac0e4e3e8039c95`。
合并补采库后，已捕获 DT_NEEDED 链完整，参考文件及可达已捕获库没有剩余强引用候选缺口。
仍不是实际重定位、dlopen 或 XOS 服务启动通过。

下一阶段 `native/xos/loader-probe.c` 在单独进程中对配套 NDK 库和 libxos
执行 RTLD_NOW | RTLD_LOCAL，然后查询四个导出函数地址，绝不调用它们。
与 --list 不同，dlopen 会执行库构造函数，退出时还会执行卸载析构；因此这是真实加载测试，
不能描述为纯静态或不执行任何参考代码。它不运行服务程序，不做 Binder 注册、VINTF/SELinux
修改、模块加载、可用性开关或 MiShare 挂载，不调用 AWDL start/stop/status/聚合配置函数。

`tools/device/popsicle-xos-loader-smoke.sh` 继续固定设备、固件、链接器及参考文件摘要，
拒绝已有 XOS/Wonder 状态。探针复制到私有目录校验，15 秒超时，比较前后可观察状态。
报告 PASS_DLOPEN_DLSYM_ONLY 只代表两次实际加载与四个符号查询成功，不代表服务或传输可用。
调用入口未启用；底层 WLAN/AWDL 后端缺口继续存在。

独立 Actions `.github/workflows/xos-loader.yml` 编译 ARM64/API31 探针，
NDK 27.2.12479018 缓存在编译前保存。宿主夹具测试也只在 Actions 编译和运行，
覆盖缺库、缺符号、相对路径拒绝及所有 XOS 导出函数一旦被误调用即失败的情况。
产物仅包含本项目探针、脚本和摘要，没有参考 APK、厂商 ELF 或安装模块。

下载 Actions 产物并解压至 Download/xos-loader-probe 后执行：

```sh
su -c 'sh /sdcard/Download/xos-loader-probe/popsicle-xos-loader-smoke.sh /sdcard/Download/XAirDrop-reference-1.0.zip /sdcard/Download/xos-loader-probe'
```

上传 Download/17pm-xos-loader-*.tar.gz。当前编译/设备结果以对应 Actions 与设备报告为准。


## 真实加载实机通过，继续服务注册诊断

设备 18:14 报告 SHA256 为
`6ecea146cafa100e765ca73c6ba21a6a11847eb7a73b880a247deee4a5498c87`。
状态 PASS_DLOPEN_DLSYM_ONLY，退出 0，前后可观察状态相同。
配套 NDK 库和 libxos 的 RTLD_NOW 加载成功，四个预期导出函数均查询成功且未调用。
这是实际构造/加载/卸载通过，不只是静态符号候选匹配；服务和无线仍未验证。

下一步脚本 `tools/device/popsicle-xos-service-smoke.sh` 对同一固定参考包做短时服务启动诊断：
固定设备/固件/链接器/原生文件摘要，要求无既有服务进程、xos0、Wonder PHY 或可用性节点。
仅运行 DomesticXOsComm 的服务入口，观察最多约 5 秒的 service check 结果，
不调用 Binder 的 start/status/stop，不更改 VINTF、service_contexts、SELinux 或 wonder_enable。
由于当前缺少系统注册配置，可能返回注册阻断；这不是完整功能失败结论，日志用于确定真实阻断点。

只清理本次启动且 /proc/PID/exe 与私有服务路径相符的进程，不使用 pkill/killall。
TERM 后必要时对仍确认属于本次启动的进程 KILL；不得杀死其他同名服务。
失败/注册阻断也打包报告，若进程无法确认退出则保留临时文件并标明检查状态。
Linux 进程所有权与清理测试在 GitHub Ubuntu 执行；本地执行环境不能可靠反映子进程 procfs。
日志只保留本次窗口中的 XOS、servicemanager 和 SELinux 拒绝相关行，不清空日志缓冲区。

成功观察注册也只记 REGISTERED_ONLY_NOT_CLIENT_OR_RADIO_TESTED。
没有观察到注册记 REGISTRATION_BLOCKED_OR_NOT_OBSERVED；结束后仍检查服务、网卡名称与 Wonder 状态。
后续需完成 Binder 客户端、必要的精确系统配置以及 WLAN/AWDL 后端，不能将本轮视为 AirDrop 可用。

下载脚本后使用现有参考 ZIP：

```sh
su -c 'sh /sdcard/Download/popsicle-xos-service-smoke.sh /sdcard/Download/XAirDrop-reference-1.0.zip'
```

上传 Download/17pm-xos-service-*.tar.gz。此脚本不是安装模块，不设置开机启动。


### 首轮服务立即退出与日志采集修正

设备 18:24 注册诊断报告 SHA256：
`8c0d7804e11182f879f0535aa2031a3b4be7ce4af64c2796c291bc71714051b7`。
未观察到服务注册，进程退出 255，前后所观察状态一致；标准输出、标准错误与筛选日志均为空。
不能单凭退出 255 判断为 VINTF、SELinux 或其他具体原因。

原采集方式在启动服务前异步启动 logcat，并且只采 Warning 以上优先级；
服务立即退出时可能来不及附加采集，INFO 日志也不会保留。
脚本现于服务启动前记录设备时间，退出/清理后等待 1 秒再按该时间窗口 dump 全优先级日志。
仅保留服务 PID、XOS、servicemanager、VINTF 和 SELinux 拒绝相关行，另存 logcat 自身错误。
不清空日志、不改权限、不添加 VINTF 或 SELinux 放行。
回归验证立即退出的 INFO/服务 PID 诊断可保留，且无关应用文本被排除。
需使用更新脚本重新获取真实退出原因，原参考 ZIP 和原加载探针无需重下载或重跑。


## 服务阻断点已确定：VINTF 声明

18:29 第二轮注册报告 SHA256：
`191c3ee13b0a372b5f9f5cfd242b9c1aec84ecf712c97e73846c2f939b2dd067`。
PID 19902 的日志确认服务进入入口并创建 DomesticXOsCommService，
在 AidlLazyServiceRegistrar 注册默认实例时返回
`Status(-3, EX_ILLEGAL_ARGUMENT): VINTF declaration error.`，随后退出 255。
没有观察到注册，前后状态一致。本轮确定了 VINTF 声明校验阻断；还不能断言声明修正后
不会再遇到 SELinux、Binder 客户端或其他问题。
PID 19868 的 Termux/untrusted_app search AVC 与服务 PID 不同，不作为该服务注册拒绝证据。
筛选器还修正为精确 servicemanager 标签，排除 MiuiDataServiceManager 的无关电话日志。

下一步模块源码位于 `modules/xos-vintf`，独立 Actions 为 `.github/workflows/xos-vintf.yml`。
模块 ID 为 `xairdrop17_xos_vintf`，只叠加以下文件：
`/vendor/etc/vintf/manifest/manifest_xairdrop17_xos.xml`。
使用 manifest meta-version 2.0、AIDL version 1、包 com.domestic.xoscomm、
实例 IDomesticXOsComm/default；AIDL 要求 meta-version >= 2.0。
该版本与格式规则见 [AOSP VINTF 文档](https://source.android.com/docs/core/architecture/vintf/objects)。

安装器限定 KernelSU/popsicle/OS4.0.5.0.XPBCNXM，检查启用的挂载元模块，并设置声明文件
为 vendor_configs_file 标签。不会写原始分区、修改 SELinux 规则或在线触碰 VINTF 缓存。
KernelSU system 目录需要挂载元模块，见 [官方模块指南](https://kernelsu.org/guide/module.html)。
通过重启让挂载与 VINTF 配置在启动流程中生效；不重启 servicemanager，不修改 apex-info-list。

模块不含 service.sh/post-fs-data/init rc 等启动脚本，也没有 APK、原生 ELF、内核模块、
system.prop 或 sepolicy.rule。禁用/移除模块并重启可移除声明叠加。
完整模块产物打包只在 Actions；测试拒绝未知文件、开机脚本或错误实例。
源文件 XML 已做结构检查，但未在本机使用 libvintf 原生解析器或设备重启验证。

安装 Actions 产物中内层 `XAirDrop-17-XOS-VINTF-0.1.zip` 并重启后，
在 KernelSU 对该模块点“执行”，或手动运行：

```sh
su -c 'sh /data/adb/modules/xairdrop17_xos_vintf/action.sh'
```

Action 先进入 init 挂载命名空间，核对挂载的声明摘要，然后使用 Download 中原参考 ZIP
执行短时注册测试；仍不调用无线 start/status/stop，不启用 wonder_enable。
如声明不可见会先停止，不能将“已安装模块”视作声明已被系统读取。
上传新生成的 Download/17pm-xos-service-*.tar.gz，再确定后续必要改动。
这只是服务声明模块，不是完整可用的 AirDrop 模块。


### Actions 下载包直接安装

KernelSU 截图报 `specified file not found in archive`，发生在读取 ZIP 根目录 module.prop
的阶段，尚未执行本模块 customize.sh。原 Actions 外层 ZIP 只含内层模块 ZIP 和 build.json，
直接安装外层会触发该错误；内层模块 ZIP 已独立核对包含根目录 module.prop。
本次无法仅凭截图确认用户选中的文件名，不将此错误归因于设备挂载或 VINTF。

现已调整工作流：打包校验后将模块内容展开到独立 installable 目录，Actions 只上传该目录内容，
产物名为 XAirDrop-17-XOS-VINTF-0.1。因此 GitHub 下载的 ZIP 根目录直接是 module.prop、
customize.sh、action.sh、service-smoke.sh、system/，可直接在 KernelSU 安装。
原打包摘要仍保留在构建日志；下载包自身摘要以 GitHub artifact 元数据为准。
这只是发布产物布局调整，声明和安装逻辑未改变，设备安装/重启效果仍待验证。
后续安装说明以本段为准，无需再解压寻找内层 ZIP。


## 声明模块安装后仍为 VINTF 错误：先核对实际视图

18:46 设备报告 SHA256：
`c66ea532757b881364120095463b625697ec6c74f5c4078eb300d587e2fa90f7`。
KernelSU 调用了该模块 Action，随后 PID 12598 服务仍在注册时返回 VINTF declaration error，
退出 255、未观察到注册，前后可观察状态一致。
Action 到达服务诊断表明按其代码路径 init 命名空间下的声明摘要检查已经通过；
这属于根据执行路径作出的推断，报告本身没有完整挂载快照。
不能据此断言 servicemanager 也看到相同文件，或证明它已经重新读取该声明。
附近其他应用/系统进程的 AVC 不作为 XOS 的 SELinux 注册拒绝证据。

本轮只增加 `tools/device/popsicle-vintf-view.sh`：对比调用者、init、servicemanager 的
挂载命名空间、声明是否可读、标签、摘要、XML、选定挂载路径以及 APEX 信息列表的时间/摘要。
记录系统启动时间、模块启用/待更新状态，以及相关 VINTF 日志，帮助区分视图、解析与缓存问题。
脚本通过 nsenter 读取目标命名空间，不更改挂载，不启动 XOS，不修改缓存、时间戳或策略。
收集的缓存文件属性本身不能证明 servicemanager 当前内存缓存内容，不能把假设当成结论。

AOSP 存在基于 APEX 信息列表修改时间检测更新的 VINTF 逻辑，
见 [Apex.cpp](https://android.googlesource.com/platform/system/libvintf/+/android16-release/Apex.cpp)。
尚未证明本机此次错误由该缓存造成，本项目本轮不触碰 apex-info-list.xml。
没有修正前的实际服务管理器视图证据，不继续叠加声明或 SELinux 放行。

使用现有模块，直接执行只读采集脚本，上传 Download/17pm-vintf-view-*.tar.gz。
本轮无需重装或另行重启，以便保留当前问题现场。


## 声明可见性确认、软重启说明与注册通过

只读视图报告 SHA256：
`27c9f470cc98d5cb24e8bc5e03c78777be2217a19e2c500a74ab72755c6bdd78`。
caller/init/servicemanager 均能读取同一声明，摘要为
`272f638bcfb54634d7b817218f5c33aef8cc6f2326fd247136f92c213870c220`，标签正确。
init 与 servicemanager 在同一挂载命名空间，本次排除了该时刻的挂载视图不可见。
当时 uptime 104051.73 秒；用户说明做过软重启，不能据此断言完全没有重启过。
在保留内核/相关服务的软重启后可能仍保留缓存，因此请用户通过普通电源菜单重启再测。

18:59 注册报告 SHA256：
`af9970dbb07bf2f2957793b2f13be569ca0e91a7184b9aba4730c8f9530a6bf5`。
服务 PID 30119 在 18:59:39.919 明确记录 Service registered successfully；
service check 曾观察到 found。18:59:43.453 服务在没有客户端时注销并正常退出，退出 0，
前后可观察状态一致。结果 REGISTERED_ONLY_NOT_CLIENT_OR_RADIO_TESTED。
末尾 not found 是此次临时 lazy 服务退出后的正常状态，不是前面的注册失败。
本报告未收集 boot ID/uptime，不能单凭它认证重启类型或证明全部缓存细节。
服务注册这一步已通过，不需要增加 SELinux 放行或再改 VINTF XML。

下一步 `native/xos/java/io/github/xairdrop17/XosBinderProbe.java`：
使用 root app_process 查询接口描述符、ping、生成 AIDL 的接口版本和哈希。
预期版本 1、哈希 5240962a28e277f0b9764b8f7d1986b35c106edb，来自固定配套原生库。
只使用元数据事务 16777215/16777214，不调用 XOS start/stop/status/config。
客户端引用释放后临时服务按原有流程清理。

该客户端不是以 MiShare 的 UID/SELinux 域运行；即使通过也只证明 root 侧协议元数据通信，
不能宣称 MiShare 应用权限通过或 AWDL 传输可用。
宿主 Java 夹具测试在 Actions 验证仅允许元数据事务，并拒绝错误描述符、ping、版本、哈希、
不支持的事务及找不到服务。Android API36 与 D8 36.0.0 在 Android DEX 编译前缓存。
构建流程为 `.github/workflows/xos-binder.yml`，设备测试脚本为
`tools/device/popsicle-xos-binder-smoke.sh`。

下载探针产物并解压至 Download/xos-binder-probe，保留已安装声明模块和现有参考 ZIP：

```sh
su -c 'sh /sdcard/Download/xos-binder-probe/popsicle-xos-binder-smoke.sh /sdcard/Download/XAirDrop-reference-1.0.zip /sdcard/Download/xos-binder-probe'
```

上传 Download/17pm-xos-binder-*.tar.gz。不需要重装声明模块，不启用 wonder_enable。
