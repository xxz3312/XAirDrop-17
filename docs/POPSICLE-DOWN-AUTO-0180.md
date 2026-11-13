# 0180 handed-off raw DOWN 的自动原生观察入口

0179 `4341e7cc30a878be7fb733c28eec48a8bc2dc61f` / Actions 43291591879 八项必需任务全部通过，包括目标诊断构建；optional ICNSS 跳过，不计入必需任务。

## 上游

本批核对 OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` 的 kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch，和 XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb` 的 module/action.sh。前者复用原生 adapter stop，后者保留原厂 CNSS2/恢复原驱动；未找到适用于本项目异步 ownership 与 CDS 停止窗口的同等实现，故在已有原生调用点作小范围接线，不替代 CNSS2。

## 行为

在已有 `mishare_cds_recovery_window` 中，MC 排空、HIF/HTC/RX 停止后，先调用 host DOWN observer，再统计 recovery candidates。observer 不释放资源、不开放窗口；HTC/HIF reset、WMI stopped/work close 等独立资格仍由原生 CDS helper 检查。

host 首先扫描 exact PSOC registry，验证 HDD/device/PDEV 身份。无匹配、foreign PSOC 或没有符合条件的 handed-off raw host 时保持原路径。存在候选时，要求原生独占 PSOC transition 和 recovering；只尝试 RTNL，竞争返回 EAGAIN，不等待。

只观察事先通过现有 handoff 将唯一所有权交还 registry 的 raw host，必须没有 prestart/session 配置、adapter 处于关闭状态。保留 host->runtime 原始槽，不转移、不复制 owner；通过 snapshot 选择首次 DOWN/raw 来源，再由 0179 的实际 runtime API 独立认证完整来源。迟到 callback、未排空、部分 timer、错误身份等错误直接传播，使此轮窗口保持关闭，后续 stop journal 继续阻止父级 close/reinit。

caller-owned host、独立 runtime、typed managed 配置请求、UP/WAIT/失败来源均不被该新入口接管。typed managed 当前只能走其已有预启动回收，不应为了连接调用方而撤销 configured START 门禁。已有 post-disable handoff retirement 继续推进实际回收和 host adapter 析构。

## 验证及边界

- 新原生 CDS fixture：64 组 raw DOWN 自动观察及完整 runtime 退役组合，检查 observer 真正位于停止后、窗口前；保留 0179 的 15 类 fault 场景。另有两类 observer 拒绝（观察前拒绝、已经保存观察后拒绝），均不允许后续窗口或清理；两项调用缺失/忽略错误变异。
- 原有 host fixture 运行实际 host C：empty/foreign/caller-owned、父级迁移、非 recovery、RTNL 竞争、缺失/UP fence、六类不合格来源，以及四种 runtime 结果传播；五项新行为变异。
- 两层分别验证：原生 CDS→runtime fixture 的 host registry 边界有显式模型；实际 host C fixture 的 runtime API 为显式模型。不能将两者合称完整原生 host+radio 一体实机证明。IRQ/固件/锁/引用/PM/DP 等物理原语仍有模型。

本地 100 项 Python 回归、语法/原生源构造/patch 检查通过；C/sanitizer 和目标编译由统一 Actions 验证，提交时待观察。保留原厂 CNSS2，不触碰 init_boot，不部署手机。configured START、AWDL 发现/握手/双向文件传输仍未因此开放。

## 完整 CI 修复记录

`7c9963a` / Actions 43329355321 的自动 native DOWN/runtime、组件、active fence、计划测试通过，六项必需任务通过；stop-admission 在 host RTNL 负例的断言识别处失败，diagnostic 在历史 parent/CDS 源指纹审计处失败。并非整轮通过，也没有实机结论。

本次修复只调整验证：为 RTNL ownership 模型断言增加明确标识，只有该变异匹配此标识，其他变异仍须匹配 DOWN host 合同断言；parent 审计只还原 exact 0180 declaration 与 candidate 前调用两处插入，保留原始 whole-file hash，不更新散列或扩大任意代码白名单。新增五项 Python 回归验证缺项、重复、参数/位置变化拒绝及无关变化仍进入原散列检查。随后重跑完整 Actions；结果待观察。
