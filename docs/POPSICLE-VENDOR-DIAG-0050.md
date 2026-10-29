# 0050 vendor Action 超时来源诊断

0049 实机 WLAN、控制节点、HAL、AP 连接和 DHCP 已通过；一次 vendor Action 返回 errno 110，未产生 native_status，随后 STOCK_RESTORED。现有日志不足以判断无线帧是否发出。

0050 仅更新用户态 action-tx，在 vendor 请求失败时输出 vendor_request_error，含 stage、errno、elapsed_ms 和 timeout_ms。kernel_reply 表示匹配请求序号的内核 NLMSG_ERROR；reply_receive 表示用户态接收等待；send / reply_parse 分别表示提交与解析失败。零 ACK、无关序号及非法正 errno 不归类为内核拒绝。诊断保持一条请求，不自动重发，不改变帧、WLAN、原生一秒完成等待或完成语义。

使用 0049 的 WLAN 包，先运行其 run 并确认 TRIAL_DRIVER_ACTIVE、Wi-Fi 已连接。将本包 action-tx-0050 复制进原工作目录并 chmod 755。不要覆盖原 action-tx 或系统驱动。

```sh
cd /data/local/tmp/xairdrop-0049
(
  [ "$(cat /sys/module/qca_cld3_peach_v2/parameters/mishare_action_tx 2>/dev/null)" = Y ] || exit 1
  FREQ="$(iw dev wlan0 link | awk '/freq:/{printf "%d", $2; exit}')"
  [ -n "$FREQ" ] || { echo 'Wi-Fi not connected'; exit 1; }
  echo "FREQ=$FREQ"
  ./action-tx-0050 vendor-action-send --dev wlan0 --freq "$FREQ" --frame action-vendor.bin --rewrite-source --timeout-ms 10000
  echo "send_exit=$?"
) > action-0050.txt 2>&1
cat action-0050.txt
dmesg > dmesg-action-0050.txt
sh popsicle-wlan-trial.sh restore "$PWD" > restore-0050.txt 2>&1
cat restore-0050.txt
cp action-0050.txt dmesg-action-0050.txt restore-0050.txt /sdcard/Download/
```

若 restore 失败，重启恢复未修改的原厂驱动。收集三份日志后再决定内核完成路径修复，不把超时解释为发送成功。
