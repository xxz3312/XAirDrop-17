# 0136 原厂 CNSS2 常驻：设备端适配器与手动 KSU 包

新增独立 stock-cnssctl/IO 适配器及 KSU customize/action/service 入口；只打包 0133 已独立验收的原始 WLAN/provider，不包含 cnss2.ko，不重写/strip ELF，不覆盖 vendor 或启动配置。service.sh 仅退出，安装/开机不执行试验；Action 明确调用一次 apply，不提供自动启动开关或失败后重试。当前不是 Apple 发现/握手/文件互传模块，无实机安装或驱动运行通过记录。

## 上游依据与差异

参考 XAirDrop 891ffe6ccf040fdc86975b4fc649add002dbebcb 的 action.sh fw()/wifi_state()/HAL 清单，以及 service.sh 的未完成启动标记；参考 OPAirDrop 28a3a1dbc9f515fa5705417a3973616e5ae6180d 的 control.sh：Wi-Fi 关闭并确认 HAL 停止后，仅替换 WLAN、保留原厂 CNSS2。

本机 0132 已发生未定位重启，故本包进一步限制为无自动加载、无普通失败自动热回退、无 AWDL 激活参数、无 mac80211/Wonder 替换。异常事务永久阻断同 boot 重放；在原厂启动恢复后可显式归档新 profile 的旧 boot 事务。上游的自动热恢复和开机自动启动暂不移植，原因是本机尚无对应生命周期运行证据。

## 设备端行为

- check/status 为只读入口，不创建事务或切换驱动。运行前严格核对 root 私有目录/文件、全部清单 SHA、固件、完整 uname、当前槽位 boot SHA、原厂 CNSS2/WLAN note/磁盘文件。拒绝原三模块包的遗留事务、旧锁、热点接口和已加载 Wonder。
- backup 只保存原厂 WLAN、副本 SHA、boot-id、当前清单摘要、原始 Wi-Fi/HAL 状态；apply 可使用同 boot 且完整匹配的 backup-only 快照。其他阶段不重放、不覆盖。
- apply 采用 0135 独立状态机。真正的内核命令只有普通 rmmod qca_cld3_peach_v2、insmod provider、insmod WLAN 三种固定目标，无用户参数、强制卸载、CNSS2 操作或 live-unload 写入。每次模块命令再次检查 Wi-Fi/HAL 已停止，原厂 CNSS2 身份持续核对。
- 框架命令 stderr/stdout 先捕获到管道，再写 root 私有日志，保留退出码；不会把共享存储日志 FD 直接传给系统服务。日志写入失败、HAL inventory 读取失败、空摘要/缺失键等均阻断。
- 日志位于 /data/adb/xairdrop17-stockcnss-logs；事务位于 /data/adb/xairdrop17-stockcnss-transaction。每个 intent/returned/done 都同步持久化，并保存内核快照；没有 pstore 时不承诺保留系统调用内部 panic 的最后日志。
- archive 只处理本 profile 的前一 boot 事务，并要求当前原厂模块/boot 身份匹配；永不自动删除或归档 0132 旧 pair 事务。

## 打包与验证

新增 stock_cnss_bundle.py 和独立 CI package 作业。输入为固定已验收 artifact 13531954238，下载后首先验证整个 ZIP 摘要，再选择两份原始 ELF，核对 SHA/note/导入版本覆盖、64 项原厂 CNSS2 接口、实际 provider 导出 CRC 以及原厂 loader 依据。包内不包含任何 CNSS2 替代品，所有文件纳入 SHA256SUMS。ZIP 固定时间戳，不依赖本地临时目录名称。

36 项本地测试通过：八项原厂导入门禁、12 项启动状态机、10 项真实 IO helper 的模型测试、六项包/归档拒绝测试。额外以实际 0133 ELF 生成约 168 MB 实验 ZIP，独立逐项验证 16 个条目、15 项摘要，两份原始模块与所有脚本和当前输入一致。体积来自保留的原始调试 ELF；未为缩小包修改二进制。CI 结果需单独取得，主机模型不替代真实 KSU 安装与 Android 系统调用检查。

## 首次手机检查边界

只在包的 CI 与下载摘要验收后提供用户安装。KSU 安装并重启后，先不要点击 Action；使用 Termux root 执行：

```sh
/system/bin/sh /data/adb/modules/xairdrop17_stock_cnss/popsicle-stock-cnssctl.sh check
```

如果提示 LEGACY_STATE_PRESERVED，应保留原 0132 事务并先核对/显式归档，不得 rm -rf 清除。首次只回传 check/status，未通过前不执行 apply。当前手机并未执行上述步骤。
