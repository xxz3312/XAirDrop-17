# 0125：原生 PCIe / CNSS2 checked 注销源码

补丁 0057 增加独立 `cnss_wlan_unregister_driver_checked_v1`，仅准入稳定、已 probe/registered 的 PEACH PCIe 设备。同步且不可终止的原生事件携带栈上的 ops/回执查询描述符，经原生 main→bus→PCIe handler 显式传入完整 remove 与 qca6290 shutdown 函数，不保留全局请求指针，不扩展 `cnss_wlan_driver` 回调结构。

平台在投递事件前设置 terminal 位；投递、准入、remove 回执或后续电源步骤失败都保留该位。旧 void 注销入口、旧 handler、普通 remove/shutdown 和注册 handler 拒绝在该位上继续操作，没有重试/重置 API。请求必须匹配实际已注册的 ops，错 owner 不更改状态。

remove 回来后，先查询外部 provider 的设备身份回执，再清 PROBED 和异步上下文；任意错误停止关机尾部，而非仅停止 EAGAIN。checked PCIe link suspend 失败也停止后续 deinit/断电。成功才清平台 ops/REGISTERED/terminal。电源尾部发生错误时不能撤销已经完成的 WLAN remove/MHI 操作，保留的是剩余所有权和终止状态；本阶段不保证回滚到可用 Wi-Fi。

补丁 0058 通过独立 `CONFIG_MISHARE_CHECKED_CNSS2_UNREGISTER` 控制原生消费者：四个 PCIe SSR/idle 槽位直接指向类型匹配的外部 provider；注册先复制 v3 描述符；注销建立引用作用域，强调用 checked CNSS2，无旧接口回退。原生 PCIe remove 在 PSOC transition 内排空操作并执行真实私有生命周期 preflight，再注销同步 lookup、调用原生 HDD remove、销毁同步对象，最后写回执。transition/私有 lifetime/上下文失败保留查找与已有 transition；PCIe link-resume-fail 的无同步特例直接拒绝。PCIe→PLD→HDD 的返回值先于其他总线注销、清 PLD 状态及组件拆除检查。

新增联合 C 夹具抽取真实 consumer、provider、原生事件路由/bus handler、完整 CNSS2 remove/shutdown 和 checked/legacy 注销函数。七个平台文件反向还原后必须逐字等于固定源码。硬件、模块 API、PSOC 同步和 HDD remove 主体由模型提供，不能认证真实平台调度/固件/加载器。覆盖两组成功（live/borrowed exit）、九组独立失败、七组准入拒绝和六项错误注入。

本地 57 项 Python 回归、原生函数组装、0057/0058 独立正反补丁检查通过。[Actions 42201870635](https://github.com/xxz3312/XAirDrop-17/actions/runs/42201870635) 的 stop-admission 作业通过，新增两组成功、九组失败、七组准入拒绝和六项错误注入，以及原有五套回归均通过 ASan/UBSan/leak detection。ZIP 摘要与六套重新组装夹具、原生片段、平台/provider/header/host 生产哈希已核对。见 [验收证据](research/popsicle-cnss-checked-0125-validation.json)。完整 CNSS2 二进制与 WLAN 配对尚未构建。默认构建不开启实验 flag，不自动替换 CNSS2、不打包为安装模块；手机未操作，无线后端保持关闭。需先完成平台二进制/旧导出 CRC、强依赖、KCFI、加载/替换顺序验证，再讨论实机。物理热拔插、native 注册失败的全部展开路径、其他恢复/电源入口和 module-exit 拒绝能力均未完整认证。
