# 0132 实机重启事件：未通过运行验收

## 已确认的事实

Termux 将输出直接重定向到共享存储时，cmd wifi status 返回 Failed transaction；更换 UID 与改从 ADB 运行未解决重定向场景。改用管道 tee 后，本次备份成功，exit 0：原厂模块副本 SHA、boot-id、清单摘要、Wi-Fi 开启状态、vendor.wifi_hal_legacy 均经脚本检查，phase 为 backup-only。该观测只支持管道方式可用，未建立 Binder 失败的底层原因。

随后 apply 期间手机重启。跟踪记录原厂 WLAN、CNSS2 移除流程已经返回，provider 插入返回成功，live 状态及 build-id note 匹配。最后持久化阶段为 intent:insert:cnss2；日志没有对应 insmod 命令、返回值或完成记录。因此只能定位到原厂卸载与候选 CNSS2 插入之间的区间，不能断言候选 CNSS2 已执行，更不能断言某个函数导致重启。候选 WLAN 加载尚未到达。

重启后的 status 显示原厂 CNSS2/WLAN 为 live，note 摘要与原厂记录一致，活动 boot 摘要未变。事务保留在 intent:insert:cnss2；不得重放或删除它后继续试验。

## 崩溃记录的限度

pstore 归档只有空目录。bootreason 两项均为 reboot。DropBox 无 SYSTEM_LAST_KMSG 或 SYSTEM_SERVER_WATCHDOG。厂商 mcrash_history 虽文件时间更新，但内容都是此前日期记录，没有本次故障条目。完整日志含 164646 行，内核环形缓冲从本次开机约 95 秒开始；没有保存上次故障栈。

crash buffer 中 init PID 1079 的 SIGABRT 使用开机未校时的时间，缺少原因和调用栈；不能据此证明其触发本次重启。重启后普通 CNSS daemon 错误也不能作为上次崩溃原因。

## 后续边界

本阶段结论为实机 apply 失败、根因未决；离线 CRC/类型/夹具验收仍只是已有静态证据，不能替代运行验收。暂停当前包的 apply/restore 重试。下一次试验前应先审查 CNSS2 平台/PCIe/MHI 卸载及异步资源生命周期，并补齐能持久化区分执行前、系统调用返回和完整完成的标记，以及重启前内核日志捕获方案。单纯延时或屏蔽错误不能当作修复。

所有上传原始日志只记录文件名与 SHA256，不将含设备网络信息的整份系统日志提交到公共仓库。证据索引见 [运行事件 JSON](research/popsicle-runtime-incident-0132.json)。本次只更新验收事实，没有修改驱动或重新编译。
