# 0140 普通 Wi-Fi 实机短时检查与 Wonder 接入边界

审查 0139 上传的当前网络及保存/实时内核日志。HAL running，5240 MHz STA 已关联，Android 网络能力包含 VALIDATED。网口 RX 为 19,399,866 字节/34,818 包，TX 为 4,753,694 字节/29,506 包；采样时网口 errors/dropped 为 0。这是普通 Wi-Fi 收发及系统连通性检查的正向证据，不是吞吐测试或长期稳定认证。

实时内核覆盖新驱动 ready 后约四分钟，未匹配到明确 Kernel panic、Oops、独立 BUG、CFI、未处理内核故障、未知符号或版本冲突记录。不能把 binder_debug 字符串误算为 BUG。peach/amss20.bin 直接查找报 -2 后走 sysfs/ueventd fallback，找到 vendor/firmware_mnt 文件，并收到 FW ready event。

日志并非全干净：缺少 qdss_trace_config_perf_v2.cfg；有 MLO/TWT/P2P peer 及 roam/速率统计等告警。hdd_get_rate_flags_he invalid params 在替换前原厂驱动日志中也出现，不能单独归因于新驱动。当前关联、收发和 VALIDATED 是观察事实，但不能由此宣称所有警告无害、完整 ABI 通过或热卸载安全。

## 下一阶段优先参考上游

已核对 Weverses/OPAirDrop 28a3a1dbc9f515fa5705417a3973616e5ae6180d 的 kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch（blob 8874b020b4d7eadea41adea787d53dcca08a3c62），原生表使用 wlan_hdd_wondertap_init/deinit/set_freq/set_filter/set_fixed_tx_rate/set_tx_rate_mask/get_capabilities，并通过 pld_set_vendor_wonder_priv_data 发布。XAirDrop 沿用其底层驱动路线，在 action.sh 中加载 radio stack 后进入 MiShare/XOS。

本项目的 kernel/popsicle-hdd/wlan_hdd_mishare_backend.c 由真实 WLAN 构建入口复制/编入，当前 managed 表 .init 指向 mishare_backend_init，仍清空 handle 并返回 -EOPNOTSUPP；频率/过滤/速率回调也拒绝，能力清单为零，mishare_wonder_attach 默认关闭。已完成的普通 Wi-Fi 加载不能等同于 Wonder 会话可用。

后续应逐项比对并复用上述原生入口，将 typed managed init/poll/retire 与现有 host/runtime/native 生命周期连接，保持原厂 CNSS2 常驻。不能用原始表强转、绕过返回值或仅开启 attach 参数来代替接入。radio backend、Wonder/mac80211 组合及 native service 仍需独立构建和实机验证后才计入 Apple 发现/握手/互传。

当前不再要求手机重复 apply 或采集同类日志。无新的 kernel 动作；本阶段只更新观察证据和接入范围。见 [0140 数据索引](research/popsicle-stock-cnss-active-review-0140.json)。原始网络日志不提交公开仓库。
