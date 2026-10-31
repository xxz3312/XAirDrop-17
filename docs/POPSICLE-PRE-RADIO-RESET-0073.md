# 0073：已完成信道/START plan、尚未请求 radio START 的 SSR 回收

扩展 0072 的显式回收：除 pre-channel PE 外，也接纳已观察信道准备成功、可选 START plan 准备成功的 INIT。任何 radio START 请求历史均拒绝，pending/失败的 PE、channel 或 plan 也继续保留资源。没有自动 shutdown caller/父资源租约，不启用无线 backend，也不生成手机测试包。

runtime 严格检查 requested/submitted/completed/ready 与 error、频率、plan 摘要的一致性。清理前捕获已完成 channel 的频率；原生 PE helper 除原有身份、原生 INIT/IDLE、空关联请求和确认定时器检查外，还核对 PE 工作频率、PE/desired HT20 宽度和 desired 中心频率。同步关闭 NDI 响应定时器后，以同一捕获值再次核对，才执行完整原生 PE 析构。未完成的准备不能因 MC flush 而被当作成功。

回收不重跑信道准备、START builder、扫描/并发授权或 MC post；后续保持 0070/0072 的 peer → 实际 DP final-free → WMA/legacy → 对象实际 final-free 顺序。原始 channel/plan 完成旗标和标量摘要保留供诊断；关闭准入后这些 ready 记录不构成再次启动授权。普通 PE/VDEV DELETE ACK 不伪造，失败 sticky、保留剩余资源且不重复析构。PE/channel/plan 的重复或矛盾通知记录独立 completion_error，首个错误保留，SSR 的 blocked 封锁标记不能抹掉先前 quarantine 原因；窗口打开后出现重复通知也禁止清理。

代码核对：原生 `lim_pre_vdev_start` 与 `lim_set_session_channel_params` 在此私有 PAS/HT20 路线上更新自身 PE/MLME/desired 字段；STA/AP 专用分支不适用。START builder 使用局部参数结构，复制出的 summary 不含命令缓冲或指针。这是源码检查；完整原生 lim_pre、内核锁/定时器与并发仍未在模型或实机执行。

新增 Actions C 模型保留 0072 全部 pre-channel 回归，覆盖 2.4 GHz / 48 信道 5240 MHz、channel-only / completed plan、同步/异步 DP、batch、额外 final-free 引用、9 类原生几何拒绝、20 类未完成/失败/矛盾/重复通知历史、timer cancel 期间的几何漂移，以及真实 radio post 后仍拒绝回收。负对照去掉原生 PE 频率比较，必须在“摘要/desired 看似匹配、PE 频率错误”的用例触发断言；完整保留此比较的对照必须先通过。

53 项本地 Python 检查、补丁反向检查与原生 API 基线还原已通过。C 模型、完整编译、严格链接和七项选定布局检查待 CI。

模型的 regulatory/lim_pre、PE 分配、其余 cleanup primitives、锁/调度器/定时器、DP/peer 物理析构和父对象仍为边界替身。尚无 radio START/UP 回收、原生自动停机/父资源协调、完整 monitor、固件/空口或 AirDrop 认证。手机无需操作。
