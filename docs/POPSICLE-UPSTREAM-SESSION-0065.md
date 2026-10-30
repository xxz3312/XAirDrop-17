# 0065：上游专用会话调用流程

0064实机静置WMA增量2，扫描窗口WMA增量34、分发34、PE入口15。help返回255时扫描请求仍提交并返回0，但扫描执行未独立认证。AWDL事件0；监听时断网退出，手动阶段未进入。原厂驱动恢复成功，关联状态未验证。不要求重跑0064。

## 缺口与本轮修改

Wonder backend的init/set_freq/set_filter仍返回EOPNOTSUPP。已有host/runtime、NDI/self-peer、PE、频道和radio组件未完整接入Wonder调用。普通STA管理帧注册不等同于上游辅助monitor和native RAW接收。

参考Leekin2/XAirDrop固定eb1fe215c6473a8dbcc6edf6cf1e67d93f250f76的PAS主机/NDI固件配置，以及OPAirDrop保留在kernel/driver的实现，新增生产session controller和host的session_step_locked入口。它在已有host/runtime上依次调用NDI CREATE、legacy/WMA/self-peer准备、PE会话、频道准备、START计划和radio START。

- 每次最多提交一个原生步骤；等待实际PE、频道和START计划完成，队列接受不算完成。
- 固定频率与平台确认的NSS，不重发已提交步骤。
- 只有radio UP且host_up返回0；仍不代表完整RX、AWDL或互传。
- 保留首次错误；SSR、draining和销毁禁止继续。销毁先永久关闭session，再沿既有runtime路径回收，保留未完成资源。
- 调用者须持有RTNL与独占psoc transition、保留父资源；EINPROGRESS时释放锁后再轮询，不能在锁下睡眠等待。
- 无自动调用或手机入口，不改变默认行为，不启用新固件会话。

新增C fixture直接执行生产controller，用模型完成事件检查异步顺序、逐步骤失败、重复轮询、参数改变、UP/host_up、SSR和逐阶段关闭。既有host fixture增加永久关闭检查，完整构建复制新header。模型不认证真实锁、固件或空口行为。

## 后续接线

仍需实现Wonder调用方的同步、平台NSS、轮询/超时及SSR/remove前回收，再接辅助monitor创建/频道/停止、完整packet DMA、接收地址过滤和native RAW投递。当前256字节header capture不能冒充完整monitor。

0065是调用流程代码增量，完整移植尚未完成；不发换壳手机包，无需手机操作。
