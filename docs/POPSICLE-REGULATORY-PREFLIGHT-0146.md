# 0146：当前国家域与 HT20 监管预检

本轮接入实际原生监管 API 的只读查询，不代表初始化参数已下发。公开 init/poll 继续关闭，手机无需操作。

## 上游与平台依据

- Weverses/OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d`，`kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch`，blob `8874b020b4d7eadea41adea787d53dcca08a3c62`：本轮重新读取原生 init 的当前国家查询/全局国家修改，并核对其信道及固定速率调用顺序。
- Leekin2/XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb`，`module/action.sh`，blob `024cd17fb19c50c10f204552f8a2cd6fffc5d30a`：本轮重新读取手动加载/回退边界，保留原厂 CNSS2；设备端脚本不变。
- 锁定的 MiCode WLAN `36df473046706a5259942e1bf7222108dbbb860f`：核对 `wlan_reg_ucfg_api.h/.c` 的 `ucfg_reg_get_current_country`，`reg_utils.c` 的三字节 `reg_read_current_country`，以及 `wlan_reg_services_api.h/.c` 的 bonded HT20/频段/passive 查询。无 CONFIG_REG_CLIENT 的 bonded 查询返回 INVALID，按拒绝处理。

上游会在初始化中改全局国家域；当前 managed 路径没有该事务的恢复和跨调用生命周期保障，因此仅接受当前域内请求，不尝试全局修改。速率/过滤/重试等实际应用仍未接通，准备成功不意味着可以 START。

## 行为

- 在已验证 HDD、非 recovery、mission mode 的新 scope 中读取当前国家域，传播查询错误。仅比较 alpha2；第三字节环境标记不参与国家匹配。请求 00 仅匹配原生 00，不表示任意国家。
- 仅支持当前 owned 信道路径的 2.4/5 GHz HT20。频率不硬编码为 5745；原生状态必须 ENABLE，且 passive 标志必须为 false。DFS、DISABLE、INVALID 和未知状态全部拒绝；尚无 DFS/CAC 协调。
- 固定速率 NSS 和启用的 RA 最大 NSS 不得超过 caller 提供的对应频段上限。此处仍未取得平台能力来源，也未验证 MCS/GI 或固件支持的速率组合。
- 每次 prepare，包括相同请求重复调用，都重新查询。失败保留已有元数据和所有权，并结束 scope。没有国家 setter、接口分配、CREATE/START 或 WMI 写入。
- 当前 scope 只序列化本次调用。不能把结果缓存为异步阶段间的监管许可或父级/组件/固件租约；未来实际配置前仍需重新验证和完整协调。

## 验证

100 项本地 Python 回归、Python 语法和 diff 检查通过。另对从生产文件原样提取的监管 helper 运行本地独立 C 行为检查，ASan/UBSan 通过；native API 使用模型，仅覆盖 helper，不是完整 host 集成。宿主 ptrace 环境不支持 LeakSanitizer，本地该项关闭；无堆分配。Actions-only 实际 host fixture 新增国家查询失败、国家不符、00 非通配、DISABLE/DFS/INVALID、passive、两个 NSS 上限、6 GHz 拒绝；覆盖 2412/5240/5745 及原生 world domain 成功、国家环境后缀、重复查询及国家/信道漂移后拒绝，并检查 scope/设备引用平衡。七项变异控制要求禁用监管检查、国家匹配、错误传播、两个 NSS 检查、信道状态或 passive 门禁后触发行为断言；待 CI 验证。

监管数据库、QDF、设备/同步和固件仍为 fixture 模型。完整目标编译、原生 C 回归及变异控制结果应以本次 Actions 为准；不计为射频或 Apple 互通验收。下一步是实际配置事务及跨调用父级生命周期保障，再连接公开 init/poll。
