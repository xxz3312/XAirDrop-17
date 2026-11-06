# 0127：恢复上游 TSF / SMMU / Wonder / Direct Refill 接口

已从 Qualcomm WLAN.LA.1.0.r1-09600-pakala.0 的原始提交 258997efffa91e0d32702e1b89d58e6cc00a5610 找到缺失实现。通过 LineageOS 镜像访问该上游提交的原始根目录，未取镜像分支的合并修改。每个引用文件的 Git blob 与 SHA256、13 个原样移植函数体的摘要均已核对，见 [来源证据](research/popsicle-cnss2-upstream-0127.json)。

原厂 cnss_get_fw_cap 的 AArch64 指令包含能力编号 5 并读取位 7；上游对应 CNSS_FW_CAP_DIRECT_REFILL_SUPPORT / QMI_WLFW_DIRECT_REFILL_SUPPORT_V01（0x80）。恢复真实的六项枚举和实际能力查询分支，没有猜测名称以碰撞 CRC，没有改写 CRC。

补丁 0061 恢复完整 TSF GPIO、时间戳 MMIO、IRQ 上半部/线程回调及释放路径；以真实 cnss_wlan_tsf_info 取代旧的单 GPIO 成员，接入正常 probe，移除原厂不存在的旧 GPIO getter 导出。SMMU getter 调用已有平台实现。Wonder 使用真实 component 绑定、设备匹配、probe/remove 和 setter，不创建虚构设备；私有 opairshare provider 的导出继续与 CNSS 区分。针对未发布私有数据的 Wonder 伴随设备，把正常 CNSS drvdata 空指针检查移到设备分类之后，确保 remove 可以清除全局伴随设备指针。

当前本地 62 项回归、补丁独立正反检查、11 个平台文件精确还原和上游函数体比对通过。真实配对构建待重跑；81 项原厂导出记录门禁保持不变，未验证的匹配不计为通过。TSF GPIO/MMIO/IRQ 和组件生命周期的实机时序尚未认证；此前 checked CNSS2 的电源/恢复并发、失败 module-exit、完整注册失败展开和 private ABI/KCFI 等限制仍适用。默认实验消费者关闭，手机未操作，无线后端保持关闭。
