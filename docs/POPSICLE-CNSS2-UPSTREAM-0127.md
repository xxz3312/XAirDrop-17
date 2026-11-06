# 0127：恢复上游 TSF / SMMU / Wonder / Direct Refill 接口

已从 Qualcomm WLAN.LA.1.0.r1-09600-pakala.0 的原始提交 258997efffa91e0d32702e1b89d58e6cc00a5610 找到缺失实现。通过 LineageOS 镜像访问该上游提交的原始根目录，未取镜像分支的合并修改。每个引用文件的 Git blob 与 SHA256、13 个原样移植函数体的摘要均已核对，见 [来源证据](research/popsicle-cnss2-upstream-0127.json)。

原厂 cnss_get_fw_cap 的 AArch64 指令包含能力编号 5 并读取位 7；上游对应 CNSS_FW_CAP_DIRECT_REFILL_SUPPORT / QMI_WLFW_DIRECT_REFILL_SUPPORT_V01（0x80）。恢复真实的六项枚举和实际能力查询分支，没有猜测名称以碰撞 CRC，没有改写 CRC。

补丁 0061 恢复完整 TSF GPIO、时间戳 MMIO、IRQ 上半部/线程回调及释放路径；以真实 cnss_wlan_tsf_info 取代旧的单 GPIO 成员，接入正常 probe，移除原厂不存在的旧 GPIO getter 导出。SMMU getter 调用已有平台实现。Wonder 使用真实 component 绑定、设备匹配、probe/remove 和 setter，不创建虚构设备；私有 opairshare provider 的导出继续与 CNSS 区分。针对未发布私有数据的 Wonder 伴随设备，把正常 CNSS drvdata 空指针检查移到设备分类之后，确保 remove 可以清除全局伴随设备指针。

本地 62 项回归、补丁独立正反检查、11 个平台文件精确还原和上游函数体比对通过。[Actions 42220557896](https://github.com/xxz3312/XAirDrop-17/actions/runs/42220557896) 的 stop-admission 作业通过：新增 6 组时间戳、4 组 GPIO/IRQ 失败路径、3 组 Wonder 生命周期和 7 项错误注入，以及原有六套回归均通过 ASan/UBSan/leak detection；七套夹具重新组装、原生/生产哈希与产物摘要均一致。TSF GPIO/MMIO/IRQ 和组件生命周期的实机时序尚未认证；此前 checked CNSS2 的电源/恢复并发、失败 module-exit、完整注册失败展开和 private ABI/KCFI 等限制仍适用。默认实验消费者关闭，手机未操作，无线后端保持关闭。


[Actions 42219949711](https://github.com/xxz3312/XAirDrop-17/actions/runs/42219949711) 已通过真实 CNSS2/provider/checked WLAN 配对构建，完整 ZIP 与紧凑报告摘要、实际三份 ELF 哈希、全部已捕获 type-inputs 已核对。

| 检查 | 实际结果 |
|---|---|
| 原厂 CNSS2 旧导出记录 | 81 / 81 的 CRC、许可证类别、命名空间完全匹配，无缺失或额外旧接口 |
| 新增 checked 接口 | 唯一新增导出 cnss_wlan_unregister_driver_checked_v1，CRC 0x45b39d2b |
| 模块记录范围内导入检查 | provider 13、CNSS2 364、WLAN 601 项匹配，模块头部记录匹配 |
| WLAN 实际导入/依赖 | 导入 checked 新接口、没有旧 void 注销导入，强依赖 cnss2 与 opairshare_wonder_provider，无未解析符号 |
| WLAN 真实 ops 表 | remove 指向原生 pld_pcie_remove；四类 SSR/idle 槽位直接指向 provider 的 PCIe 函数 |
| 入口前置数据字 | 81 个旧 CNSS2 导出与原厂一致；4 个 provider PCIe 回调与原厂 WLAN 原生槽位函数一致 |
| 能力查询指令 | 未重定位 cnss_get_fw_cap 函数字节 SHA256 与原厂一致，fw_caps / sku_features 读取偏移分别为 0x1d80 / 0x1d88 |

这是完整配对链接与记录检查验收，尚未安装到手机。入口前置字、两处字段偏移与单个函数的未重定位字节只覆盖明确范围，不认证所有 KCFI 调用点或全部私有结构。默认完整诊断工作流仍另行运行，不计为 checked 配对已实机运行。下一步优先协调完整注册失败展开、安全卸载/已退出状态和部署替换流程，再准备实机测试。GPIO/MMIO/组件硬件并发、模块加载器/失败 module-exit、RF 与 Apple 发现/握手/双向传输仍未验收。见 [机器证据](research/popsicle-cnss2-upstream-0127-validation.json)。
