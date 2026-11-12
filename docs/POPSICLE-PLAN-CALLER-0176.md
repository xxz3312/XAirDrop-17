# 0176 完整请求的 START-plan 提交调用链

0175 修正版 `e96839c55a12573972e2218a2e2e5de4d6355da9` 的 [Actions 43231437844](https://github.com/xxz3312/XAirDrop-17/actions/runs/43231437844) 八项必需任务全部 success，含完整目标构建、host/原生生命周期和 0175 提交组合。

本批再次检查两个上游，主分支均未变化：Weverses/OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d`，参考 `kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch` 的 create→start→错误退出；Leekin2/XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb`，参考 `module/action.sh` 的启动/失败恢复顺序。上游同步启动不能替代本项目异步 owner、跨轮询 identity 和 qualified SSR 合同；沿用已有 native encoder/0175 commit/退出，不重写驱动。保留原厂 CNSS2，不触碰 init_boot。

## 实现

新增 `mishare_wonder_managed_plan_commit_step` → request bridge → `mishare_wonder_host_plan_commit_step_locked` → `mishare_runtime_start_plan_commit` 内部调用链。它只提交**已经完成**的编码预览：缺少预览或工作未排空返回 EINPROGRESS，不创建 host、不推进配置、不重放 preview；预览失败原样返回。runtime 的 registry/一次性提交及 native 退出维持 0175 合同。

每轮 managed 调用 claim 实例、打开新的 native transition/RTNL scope、先核对 pinned 父级，使用原实例的冻结完整请求和唯一权威 host。request bridge 将只读请求/身份/当前策略检查提取为 shared validator；旧 ready 和新 commit 都重新解析 canonical 请求、核对所有字段与 HDD/NSS、读取当前 native 国家域/监管政策。新入口不调用旧 pre-plan observer，避免它在第一次提交后拒绝合法重复轮询；也不缓存上次的 ready。

新增纯 `mishare_start_plan_commit_check`，与旧 observer 共用完整配置检查，额外验证 preview 的 requested/posted/completed/错误、精确 ID/frequency、原生选定频段 NSS、七字段编码摘要及 committed 标志/NDI plan 的对应关系。已提交计划仍需每次验证当前配置、prestart/session、工作排空和退出/SSR 历史。函数不改写/投影实际状态；旧 `mishare_start_ready_check` 继续拒绝任何计划历史，旧 preview 入口在提交后仍拒绝重放。

host 完成 fresh parent/context、DOWN/netdev 和一份 coherent snapshot 检查之后才调用 runtime commit，返回路径释放 scope 和 instance claim。普通退出、SSR 等待/关闭/回收均沿同一个 embedded bridge，不分配或复制 owner。

## 验证

- 原纯观察 16 组合、56 边界及九项变异保留；新增 32 组计划提交前/后的只读组合、35 项边界/缺少预览/等待/错误场景及六项新变异。
- request bridge 增加三个实际 host 结果、请求变更/当前策略/关闭拒绝和三项新变异；验证新调用不经旧 ready、不推进准备。
- 完整 host fixture 增加普通退出和 SSR 两种 caller 模式、12 类保留边界、五项新行为变异。检查 pending 返回、重复成功、旧 preview 不重放、提交后策略变化仍先拒绝；SSR partial batch 保留原 host/父级登记，关闭后拒绝提交，实际 batch 完成才清理 owner 和 metadata。父级拒绝还检查 native context 尚未读取，防止被下游重复身份检查掩盖。
- host snapshot/runtime commit 返回、native locks/ref/调度和物理原语仍有模型边界；真实 runtime 提交/MC/native encoder 与 192 SSR/160 ordinary 退出由本轮保留的 0175 fixture 独立回归，不把两种 fixture 拼称一个真实端到端测试。

本地 100 项 Python 回归、py_compile、diff 检查、纯 fixture 源码组合和各变异唯一性检查通过，不执行本地 C 编译。原生/sanitizer 和完整目标构建集中交给本轮 Actions；提交时结果待观察。

仍未开放真正 radio START/UP、公开 init/poll、过滤/数据面，也未验证 active START/UP 的退出和 SSR。新入口成功只代表主机计划采纳与当前请求一致，不是可缓存的 native/firmware readiness lease。真正 START 必须重新检查 native 编码器与当前请求/父级、并先完成 active 生命周期合同。手机无需操作；不生成部署包。
