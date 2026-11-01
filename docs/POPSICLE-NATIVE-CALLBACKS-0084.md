# 0084：原生 MLME 回调分派与 PAS ops 绑定

0083 已执行原生 SM create/destroy，但主流程仍用转调 controller 的回调适配器。本阶段编入固定版本的 12 个原生 inline 分派函数、完整 `struct vdev_mlme_ops` 声明和 32 槽 PAS 表，覆盖 validation、START/continue、beacon、UP/complete、disconnect、STOP/continue、DOWN/complete 及 START exit。

每个 adapter 分别检查 NULL ops、NULL slot 的原生默认 SUCCESS 且零调用行为，以及上下文、长度、数据、beacon op、legacy 标志和 SUCCESS/FAILURE/NOSUPPORT 的原样传播。默认 SUCCESS 不能证明无线动作完成，因此另对完整 PAS 表的每个槽位核对目标函数，并以遗漏 START 绑定、吞掉回调失败两个负对照证明检查有效。

八种主流程保留原生引擎和创建/销毁入口；已有五项引擎/owner 负对照继续执行。validation/down 两个表目标使用明确命名的测试探针，保留原有竞态与来源注入后调用实际 controller；其余沿用原始绑定。报告分别记录原始表/类型/函数哈希和这两个探针，不宣称表目标完全未经测试插桩。

Python 语法与 12 个原生函数提取检查通过，完整 Actions 验收待完成。

完整 ops 声明不构成私有 ABI/布局认证。对象字段、锁/minidump、内存与外部响应分派/transport、完整 WMA 后处理仍有模型；完整 object-manager 调用方、物理 DP/peer 生命周期、父资源自动协调与实际 START/UP SSR 恢复仍未覆盖。未开启 backend，无新手机测试包或固件/RF/AirDrop 可用证明。
