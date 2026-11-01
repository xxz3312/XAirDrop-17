# 0086：普通 DOWN 后完整清理组合验证

0085 的完整 WMA/SM 生命周期继续经过原生 PE 析构、普通 WMA peer 删除、固件 peer/VDEV DELETE 响应、DP 完成、WMA/legacy 释放、原生 SM 销毁与 VDEV 最终释放。普通路径使用完整原生 `wma_remove_peer` 和 `wma_remove_objmgr_peer`，以独立端点模型编译为 clean_native_*；不复用 SSR/no-FW force detach。

新增 32 种串行回调/引用组合：peer ACK、peer unmap、DP VDEV 完成、VDEV DELETE ACK 的提前或延迟，及外持 VDEV 引用。外持引用与 flush-service 能力共用一个测试位，两分支都有覆盖，不宣称六个独立维度的全部组合。保留 16 种 WMA 主流程和三次 ratemask 流程，均继续完成清理。

六类失败覆盖 PE DELETE flush、peer 发送错误后晚到响应、peer 超时、VDEV 超时、DP detach 拒绝、host 对象删除拒绝；检查尚未完成的资源保留，而非宣称已释放的资源回滚。新增移除生产 peer ACK 等待和 DP 完成等待的两个负对照，连同此前九项负对照运行。

CI [41275178699](https://github.com/xxz3312/XAirDrop-17/actions/runs/41275178699)（`388b029`）已全部通过：53 项 Python 检查、16 种 WMA 主流程与三次 ratemask 流程接续完整清理、32 种新增回调/引用组合、六类新增失败保留、既有八类 WMA 失败保留、11 项负对照、0085/0084/0083/0082 独立模型与旧 C 回归、完整编译、CNSS 名称检查、严格链接、七项选定布局及最终模块记录检查。39 份模型报告的公共生产源码哈希一致，五个生产文件已独立核对；两个普通 WMA 删除函数与固定源码独立匹配，owned peer 删除入口与 0017 补丁一致。完整生成源码在本地从固定快照与既有补丁重建，SHA-256 与 CI 匹配；本地未执行 C 编译。报告 ZIP 校验值及实际链接模块/布局候选均已核对，WLAN 无未解决依赖，五个模块均无版本记录不匹配或缺版本依赖。本阶段离线验收完成，见[验证记录](research/popsicle-native-cleanup-0086-validation.json)。

peer 引用/逻辑删除/unmap、DP teardown/callback、WMI transport、component destructor 调用方与父列表仍是平台模型。模型明确将 DP VDEV 最终完成延迟至 peer unmap/逻辑删除完成；这不能认证真实 DP/peer 对象析构图或硬件顺序。原生 SM 销毁在模型组件析构的 VDEV 零引用处执行，先于原生父列表 detach、VDEV storage free 与 runtime 最终通知。父资源由测试框架保留，不代表自动 native parent lease/coordinator。

活动 START/UP SSR 恢复、真实并发停机与安全模块卸载、完整 AWDL 收包仍待后续工作。backend 关闭，无新手机包或固件/RF/AirDrop 可用证明。
