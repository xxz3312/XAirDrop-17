# 0084：原生 MLME 回调分派与 PAS ops 绑定

0083 已执行原生 SM create/destroy，但主流程仍用转调 controller 的回调适配器。本阶段编入固定版本的 12 个原生 inline 分派函数、完整 `struct vdev_mlme_ops` 声明和 32 槽 PAS 表，覆盖 validation、START/continue、beacon、UP/complete、disconnect、STOP/continue、DOWN/complete 及 START exit。

每个 adapter 分别检查 NULL ops、NULL slot 的原生默认 SUCCESS 且零调用行为，以及上下文、长度、数据、beacon op、legacy 标志和 SUCCESS/FAILURE/NOSUPPORT 的原样传播。默认 SUCCESS 不能证明无线动作完成，因此另对完整 PAS 表的每个槽位核对目标函数，并以遗漏 START 绑定、吞掉回调失败两个负对照证明检查有效。

八种主流程保留原生引擎和创建/销毁入口；已有五项引擎/owner 负对照继续执行。validation/down 两个表目标使用明确命名的测试探针，保留原有竞态与来源注入后调用实际 controller；其余沿用原始绑定。报告分别记录原始表/类型/函数哈希和这两个探针，不宣称表目标完全未经测试插桩。

CI [41270857085](https://github.com/xxz3312/XAirDrop-17/actions/runs/41270857085)（`01b6203`）已全部通过：53 项 Python 检查、新原生回调模型、12 个 adapter 的 60 项空槽/参数/返回值契约检查、完整 32 槽绑定、八种主流程、七项负对照、0083/0082 独立模型与既有 C 回归、完整编译、CNSS 名称检查、严格链接、七项选定布局和最终模块记录检查。37 份模型报告的公共生产源码哈希一致，五个生产文件已独立核对；12 个函数与原生 ops 类型哈希匹配，PAS 表从 0011/0022 补丁独立重建后匹配。整个 ops 头文件与原始固定源码的差异来自既有 0007 补丁的 PASSTHRU 类型宏/注释，重建后的整文件哈希也匹配，ops 声明没有差异。报告 ZIP 校验值与实际链接模块/布局候选记录均已复核，WLAN 无未解决依赖，五个模块均无版本记录不匹配或缺版本依赖。 本阶段离线验收完成，见[验证记录](research/popsicle-native-callbacks-0084-validation.json)。

完整 ops 声明不构成私有 ABI/布局认证。对象字段、锁/minidump、内存与外部响应分派/transport、完整 WMA 后处理仍有模型；完整 object-manager 调用方、物理 DP/peer 生命周期、父资源自动协调与实际 START/UP SSR 恢复仍未覆盖。未开启 backend，无新手机测试包或固件/RF/AirDrop 可用证明。
