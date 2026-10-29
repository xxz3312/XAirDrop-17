# 按小米 15 上游流程适配的手动 WLAN 测试（0047）

参考 Leekin2/XAirDrop 当前 main（核对仍为 eb1fe215c6473a8dbcc6edf6cf1e67d93f250f76）的 module/action.sh、service.sh 与 customize.sh。源码和许可来源保留在 third-party/xairdrop15。action.sh 的实际做法是在 RAM 中临时替换驱动：关闭 Wi-Fi、停止运行中的 vendor.wifi_hal 服务、正常卸载原驱动、加载新驱动、恢复 HAL/Wi-Fi，失败时尝试恢复原驱动。service.sh 则在 boot_completed 后等待再调用 action.sh，并有上次启动未完成时跳过的标记。它不依靠在 early-init 前覆盖模块文件。

17 的 vendor.modprobe 确认在 early-init 启动，优先从 /vendor_dlkm/lib/modules 读取 modules.load；/vendor/lib/modules 是同目录的符号链接。因此沿用上游的手动运行时切换路线。0047 暂不接入自动启动，先验证 17 自编译 WLAN 的实际加载和 vendor Action。

## 0046 实机问题及修复

0046 校验正确，但内核报告 `Unknown symbol opairshare_set_wonder_priv_data (err -2)`：WLAN 有强导入，包遗漏了本项目的 `opairshare_wonder_provider.ko`。因此 insmod 的 ENOENT 不代表文件不存在。自动恢复原 WLAN 后，采集时尚未关联 AP。

0047 沿用同一次 0045 CI 的 WLAN 和工具，补入同源、同构建的 provider，不重新编译 WLAN。run 在关闭 Wi-Fi/卸载原 WLAN **之前**正常加载 provider；失败立即退出，保留正在工作的 WLAN。check 仍为只读，只核对包与环境，实际内核兼容性由 run 加载验证。已有 provider 时拒绝接管，避免卸载他人会话。保存本次 provider 所有权，恢复时先卸载实验 WLAN、加载原 WLAN，再卸载本次 provider。保留原 CNSS 模块与导出，不强制加载。

## 本机适配

- 使用 0045 的原生 6.12 WLAN，不使用 15/SM8750 的 6.6 二进制，不改 CRC 或强制加载。
- 仅替换 qca_cld3_peach_v2；保留系统 cfg80211/mac80211/CNSS。会先加载本项目原生 6.12 的 opairshare_wonder_provider；不会加载 15 的 oneplus13_wonder_provider，也不复制尚未移植的 passthru 参数。
- 手动脚本提供 check/run/status/restore；run 才会关闭 Wi-Fi、停止原先运行中的 HAL、正常 rmmod/insmod。原驱动文件、modules.load、init 和分区保持原样。状态与锁位于 /dev，重启后由原启动流程加载原驱动。
- WLAN 加载参数只有 mishare_action_tx=1、mishare_raw_tx=0。这不是完整 NDI/AWDL 配置。
- 运行前核对机型/kernel、boot_completed、已加载原 WLAN、无 Wonder/热点、已知 Wi-Fi 状态、识别出的运行中 HAL 和包校验。无法确认即拒绝切换。
- 原驱动忙不强制卸载。加载失败或 wlan0/Wi-Fi 未就绪时尝试恢复原驱动及原 Wi-Fi/HAL 状态。脚本无法恢复内核崩溃；重启会重新加载未修改的系统原驱动。
- 生产 shell 脚本在模拟 Android 命令/文件系统中执行，覆盖 14 个成功、失败、恢复和拒绝路径。这不是内核卸载/加载实机认证。

CI 从已通过构建 40841130362 提取原始 WLAN，核对 SHA256，再用固定 NDK 27.2.12479018 llvm-strip --strip-debug 去除调试信息；不重新编译、不修改 CRC。工具取自 40841130477，源码 d8365331d8920786fcdb345a31679347d7903273。包附代码来源、SHA256SUMS、许可和对应项目源码。

## 1. 结束现有 Wonder 测试

先确认旧中继已退出、关闭热点。在旧 root 工作目录，若 Wonder 仍加载：

```sh
cd /data/local/tmp/xairdrop-0040
sh popsicle-rx-start.sh stop
```

若本次测试的 misharemon0 仍存在，再执行：

```sh
ip link set misharemon0 down && iw dev misharemon0 del
```

检查脚本也会拒绝仍加载 Wonder 的环境，不自行卸载未知 Wonder 会话。

## 2. 准备与只读检查

解压到 Download 后复制到临时工作目录。用手机本地 root 终端操作，切换过程中 Wi-Fi 会断开；保持电量和本地终端可用。

```sh
cp -R /sdcard/Download/XAirDrop-17-WLAN-Trial-0047 /data/local/tmp/xairdrop-0047
cd /data/local/tmp/xairdrop-0047
chmod 755 action-tx
sh popsicle-wlan-trial.sh check "$PWD" > check-0047.txt 2>&1
cat check-0047.txt
```

应出现 CHECK_OK。若失败，先发 check-0047.txt，不继续 run。

## 3. 手动切换本次开机的 WLAN

```sh
sh popsicle-wlan-trial.sh run "$PWD" > trial-0047.txt 2>&1
cat trial-0047.txt
```

成功标记 TRIAL_DRIVER_ACTIVE 只说明模块和 Wi-Fi 就绪，不代表已关联 AP、固件接受 Action 或 AWDL 可用。若出现 RESTORE_FAILED，重启以恢复原驱动，不重复 run。

## 4. 一次实验 vendor Action 发送

成功后连接原 Wi-Fi，再运行：

```sh
(
  FREQ="$(iw dev wlan0 link | awk '/freq:/{printf "%d", $2; exit}')"
  [ -n "$FREQ" ] || { echo 'Wi-Fi not connected'; exit 1; }
  ./action-tx vendor-action-send --dev wlan0 --freq "$FREQ" --frame action-vendor.bin --rewrite-source --timeout-ms 3000
  echo "send_exit=$?"
) > action-0047.txt 2>&1
cat action-0047.txt
```

实验帧 category 127 / OUI 02:00:00 / XAIRDROP0047_TEST，广播 DA/BSSID、占位 SA（显式 rewrite-source 替换）。不是 Apple AWDL 报文。vendor_action_tx_status native_status=0 才说明实际收到原生完成回调，仍不证明对端接收。不自动启动 XOS/MiShare 或设置 wonder_enable。

## 5. 恢复与日志

发送后优先恢复原驱动：

```sh
sh popsicle-wlan-trial.sh restore "$PWD" > restore-0047.txt 2>&1
cat restore-0047.txt
dmesg > dmesg-0047.txt
cp check-0047.txt trial-0047.txt action-0047.txt restore-0047.txt dmesg-0047.txt /sdcard/Download/
```

如 restore 失败，重启后原驱动文件会按系统原有 early-init 流程加载。不要手动删除或覆盖系统模块。若后续另行启动 Wonder，先停止其桥接再 restore。
