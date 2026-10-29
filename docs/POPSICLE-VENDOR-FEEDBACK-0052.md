# 0052：单终端 vendor Action token 测试

0052 增加 shell 控制器，复用 0051 工具、Wonder 和实验广播帧，以及 0049 WLAN。没有修改 C、驱动或发送参数。0051 完整 token 闭环仍待手机验证；0050 只验证了一次直发原生完成。

本控制器等待 relay_ready 后只注入一次，要求 native_status=0、token outcome=1、completed/reported=1、failed/rejected=0，并在清理成功后输出 TOKEN_TEST_PASS。NOACK=1 不代表对端接收或 Apple ACK。

## 运行

先按 [0051](POPSICLE-VENDOR-FEEDBACK-0051.md) 准备原始测试包、chmod 755 action-tx-0051，并启动 0049 实验 WLAN、连接 Wi-Fi。停止旧 relay/Wonder 会话，清理此前自己创建的 monitor。无需启动 LPC、无需第二终端。

把本仓库 tools/device/popsicle-vendor-feedback-test.sh 保存到 /data/local/tmp/xairdrop-0051 后，在 root 本地终端运行：

```sh
cd /data/local/tmp/xairdrop-0051
sh popsicle-vendor-feedback-test.sh "$PWD" "$PWD/result-0052-01"
```

日志目录必须不存在。再次执行使用新目录，如 result-0052-02；脚本不自动重试。全局锁防止两个控制器同时运行。中断后先确认旧进程及其资源已结束，再处理遗留锁 /data/local/tmp/xairdrop-vendor-feedback.lock。

脚本只拥有本轮创建的 xfbtmon0/Wonder/relay，拒绝现存资源。动态读取 STA 频道，注入前重查，频道变化则中止；不会执行 native monitor 换频，也不会停用 P2P/NAN。此轮只验证 TX token 路径，不开启 LPC RX。模块加载或接口创建因设备并发限制失败时，保留日志，不自动修改其他接口。

退出及 INT/TERM/HUP 时终止并等待 relay，再停止本次 Wonder，最后删除 xfbtmon0。Wonder 停止失败会保留 monitor，返回非零并显示 CLEANUP_FAILED。此时先解决 Wonder 占用，不恢复 WLAN、不强制卸载。脚本失败不会输出 TOKEN_TEST_PASS。

## 恢复和收集

确认清理成功后，恢复原厂 WLAN：

```sh
cd /data/local/tmp/xairdrop-0049
sh popsicle-wlan-trial.sh restore "$PWD" > /data/local/tmp/xairdrop-0051/result-0052-01/restore.txt 2>&1
cat /data/local/tmp/xairdrop-0051/result-0052-01/restore.txt
cp -R /data/local/tmp/xairdrop-0051/result-0052-01 /sdcard/Download/
```

需要反馈 feedback.log、result.txt、stop.txt、restore.txt；失败时附 setup.txt、inject.txt（若生成）和 dmesg.txt。原始日志可能含设备信息，请只私下上传，不提交公共仓库。

## 验证边界

Python 模型执行实际 shell，覆盖成功时单次注入/清理顺序、已有 Wonder/monitor/锁拒绝、校验失败、STA 断开、就绪前退出、频道变化、注入失败、错误 ACK 证据、启动失败和卸载失败。模型不认证手机 shell/驱动、射频接收、AWDL 或完整私有 ABI。CI 还执行已有协议/反馈模型和 Android 构建；实机待测。
