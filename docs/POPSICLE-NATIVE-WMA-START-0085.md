# 0085：原生 WMA START 响应后处理

0084 的 WMA START 响应仍由简化函数直接投递 SM 事件。本阶段替换该函数，编入完整 `wma_vdev_start_resp_handler`，以及原生 MAC/DP MAC 更新、频道切换响应和 ratemask 类型转换函数。四个函数体从固定版本源码加既有 0015 PAS/NDI 兼容补丁独立重建并与 CI 输入核对，不修改生产驱动源码。

主流程覆盖 INIT/0 或 IDLE、2437/5240 MHz、普通/提前响应及直接 MAC/pdev→MAC 映射共 16 种组合；检查 BSS 频道完整复制、TX streams、主机/DP MAC ID、功率字段和 START_RESP 参数在进入 UP 前就绪。保持原生 `sizeof(rsp)` 的指针长度表达式，不将它写成整个响应结构长度。另覆盖四类有效/两类无效 ratemask 类型转换、有效配置发送、发送失败仅记录并继续，以及越界配置跳过三次完整流程。

八个失败用例覆盖缺少 WMA/MAC/config/resource、非法 pdev ID、缺少 MLME 对象、UP 后 WMI handle 校验失败，以及 SM 拒绝 START_RESP。特别检查：WMA 可在频道/MAC 已修改后失败，也可在 UP 后失败；原生频道助手忽略事件返回值，但生产 controller 的 phase 检查仍封锁并保留资源，不伪造回滚或恢复。

已有七项负对照保留，新增遗漏 BSS 频道复制、遗漏 PAS/NDI DP MAC 更新两个负对照。0084/0083/0082 独立模型继续单独运行。CI [41273213537](https://github.com/xxz3312/XAirDrop-17/actions/runs/41273213537)（`82baf02`）已全部通过：53 项 Python 检查、新完整 WMA 响应模型、16 种主流程、3 次额外 ratemask 流程、6 项类型映射契约、8 类失败保留、九项负对照、0084/0083/0082 独立模型与既有 C 回归、完整编译、CNSS 名称检查、严格链接、七项选定布局及最终模块记录检查。38 份报告的公共生产源码哈希一致，五个生产文件已独立核对；四个函数体从固定源码加 0015 补丁重建后匹配，ratemask 类型、回调/PAS 表与独立模型哈希一致。完整生成源码也已在本地从固定源码快照与补丁重建，与 CI 生成源码哈希一致；本地未执行 C 编译。报告 ZIP 校验值及实际链接模块/布局候选均已核对，WLAN 无未解决依赖，五个模块均无版本记录不匹配或缺版本依赖。 本阶段离线验收完成，见[验证记录](research/popsicle-native-wma-start-0085-validation.json)。

上下文/config、WMA/MLME 字段、锁/minidump、DP MAC/policy 与 ratemask transport 仍是平台模型；完整函数体不代表全部传递调用或实际 firmware 执行。未选择的 AP/STA/OCB/restart 路径绑定中止 stub；提取函数范围内禁用 FEATURE_AP_MCC_CH_AVOIDANCE，不能据此宣称覆盖真实内核的所有条件配置。validation/down 两个表探针保留，SM delivery bridge 增加明确的 START_RESP 参数/副作用观察及一次故障注入。失败子用例保留资源直到进程范围结束，不认证物理析构/原生调用方顺序。

物理 PE/peer 生命周期、父资源自动协调和实际 START/UP SSR 恢复仍未实现/验证。backend 关闭，无新手机包或固件/RF/AirDrop 可用证明。
