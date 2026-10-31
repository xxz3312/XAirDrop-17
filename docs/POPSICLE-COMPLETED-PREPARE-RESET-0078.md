# 0078：START 准备成功、尚未提交 SM 的 SSR 回收

在 0077 准备入口门槛上新增一个受限分支：原生 START 准备完整成功，重新读取的原生编码器摘要与原先完成的计划逐字段相同，SSR 在任何 START SM 提交之前到达。失败/部分准备、摘要不匹配或已提交 SM 均继续保留资源。

radio_open 按值保存完成计划的七项 u32，不借用 caller 存储；runtime 传入自身已完成计划。准备调用返回成功后重新调用已有原生 encoder builder，比较 freq、center_freq、phy_mode、tx_streams、rx_streams、beacon_interval、dtim_period，全部相同才记录 start_prepare_succeeded。SM 提交记录在调用 radio_sm 之前、与 quiesce 相同的锁下保存。即使 SM 尚未实际进入、VDEV 仍为 INIT，只要提交记录已经成立，也不推断可回收。

SSR 可以为准备已进入、SM 尚未提交且无执行/回复/MLME users 的 pristine NEW controller 记录候选；只有准备最终完整成功且摘要匹配，才产生私有/observable prepared-abort 事实。callback 在 work_exit、请求内存释放、work reservation 与 pending 归还之后发布独立 runtime origin，之后不再访问 controller。五种取消来源要求恰好一项，重复/混合通知保留 sticky completion_error，外来身份不解引用。

合格 SSR 窗口中先复核 PE/context，再对 controller/INIT/空事务/零 users/pending/未提交 SM 进行检查。当前原生 encoder 摘要在 radio 锁外重新构建并与原值比较，timer drain 后的 release 再运行一次检查；任何参数漂移都拒绝 controller 退休。退休后沿用 PE → peer → 实际 DP final-free → WMA/legacy → 对象实际 final-free。保留 radio_requested、BLOCKED/ESHUTDOWN 和 prepared-abort 历史，不制造 START/STOP/DOWN、普通 ACK 或重试。

本轮无新增 native patch。START 准备仍沿用固定版本原生 channel/start-plan 链，成功以后才允许本分支；额外 summary 构建使用已有 MOBILE_DFS/PAS 限定 builder，不构造持久 WMI command，不调用 target-if。源审查沿用并核对 0073 的 lim_pre_vdev_start、lim_set_session_channel_params 和 native encoder 路径；这不是对全部传递调用的执行认证。

新增 Actions 模型保留 0077 回归，执行生产 runtime/radio、native builder 和 PE/peer 路径；覆盖双频、inline/deferred DP、准备入口/成功返回处 fence、batch、窗口关闭后的延迟 final-free、caller 计划拷贝、20 类拒绝、七项保存计划及当前原生参数漂移、timer drain 中漂移、准备完成但摘要不匹配、SM 提交时 fence。两个负对照分别移除私有 prepared-abort 检查、移除当前 native plan 重检，必须均被测试发现。

CI [41193377121](https://github.com/xxz3312/XAirDrop-17/actions/runs/41193377121)（源码 `fe1ecaf2ea25f4542aca12b665f140b6f64f5e04`）已通过 53 项 Python 检查、新模型及私有 prepared-abort/当前 native plan 两个负对照、既有全部 C 模型、完整 WLAN/Wonder/provider 编译、严格链接和七项布局检查。五项生产源码哈希、八组模型间公共哈希、七个 native 文件哈希、新 origin 实际链接及模块依赖记录已复核。验证 ZIP SHA256 为 `3a451474502193ca625da9d8bdf2b216fe8da13251de106509776a188d15807c`，详见[验证记录](research/popsicle-completed-prepare-reset-0078-validation.json)。生成模型源码哈希记录自 CI，未在本地独立重建。公开 Wonder ops/priv ABI 不变；内部 radio_open 参数更新，WLAN 和模型共同构建。

显式 caller 仍须保留并串行原始父资源，完整 scheduler/QDF/锁/定时器、原生 SM/WMA 后处理、PE 分配及其余 cleanup、DP/peer 物理生命周期和父资源仍含模型。SM commit 只是严格拒绝回收的门槛，不是覆盖完整 native dispatch 的原子封锁。实际 SM/START/UP、自动 shutdown/父资源协调和完整接收路径仍未完成；backend 关闭，不制作新手机包，不证明驱动加载、固件/RF 或 AirDrop。
