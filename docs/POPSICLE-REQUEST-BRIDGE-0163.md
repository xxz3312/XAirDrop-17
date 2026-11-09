# 0163：完整请求绑定到内部 pre-START 桥接

## 参考与范围

修改前重新读取 Weverses/OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` 的 `kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch`，核对 init 中 country、BSSID、固定速率和 retry 的处理；读取 Leekin2/XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb` 的 `module/action.sh`，继续保留原厂 CNSS2 与手动部署/恢复合同。

本轮不直接套用上游同步初始化：本项目的 host/MC/退出是异步分步，跨调用父级和完整全局配置事务尚未具备。新增内部 request-bound 桥接消费已有规范化请求格式，将其接到已验证的 prestart controller；没有连接公开 managed step，原 request_prepared 对 raw step 的 EOPNOTSUPP 保留。

## 生产实现

`mishare_request_bridge` 嵌入原有 authoritative bridge 和完整 `mishare_init_request`。第一次 poll 先解析/规范化，再调用新的只读 native preflight；拒绝时不分配 host、不绑定参数。成功后在分配前冻结请求并标记 prestart 模式和 one-shot 尝试。

后续 poll 对整个请求做语义比较，包括 MAC、BSSID、country、频道、速率、retry、聚合及有效自适应字段；变更返回 EBUSY，保留原请求和资源。保留字节、未启用 adaptive mask 仍规范化忽略。父级/NSS 不可替换，桥接 MAC/频率投影出现矛盾则永久失败。

每次 allocation、attach 或 prestart 之前，都在 caller 已持有的 RTNL/exclusive native transition 下重新运行 native preflight：有效上下文、非 recovering、mission mode、支持的固定速率/HT20、当前国家域一致、对应频段 NSS 上限、信道 ENABLE 且非 passive。国家域不会被修改。首次策略拒绝不绑定；已绑定后的策略失败记入原 bridge.start_error，保留同一 host 槽供退出，禁止盲目重试。

host 分配、runtime attach 分别一次尝试。实际 prestart 只读取内部冻结请求的频率/速率和冻结 NSS，不再从各次 poll 的散装参数取得输入。成功零返回只表示当前准备子集完成，不是完整 init、radio UP、固件 ACK 或 RX/TX readiness。原 raw bridge step 遇到 prestart_mode 返回 EBUSY，避免切回原无配置 START 链。

退出/idle handoff 继续通过嵌入 bridge；partial create 错误保留 authoritative host 槽，不清空、不接管外来对象、不增加第二套释放协议。调用方仍须保留同一 HDD/components/firmware/模块文本并串行 poll，新增结构不会自动取得 parent lease。

**尚未应用的字段：**BSSID、retry、聚合等完整请求字段本轮仅保存在 immutable snapshot；国家码只核对当前域。没有把“保存了参数”写成“固件已配置这些参数”。

## 验证

本地 100 项 Python 回归、语法与 diff 检查通过。编译/ASan/UBSan 只在 Actions。

新增 request bridge 夹具包含实际 bridge/init/request headers，host allocation/attach/prestart/retirement 与 native scope 是模型：8 组 metadata/rate 成功模式、15 个有效字段变化、规范化等价请求、首次及后续策略拒绝、partial create/attach/prestart 失败、one-shot、raw 路径拒绝、投影矛盾及 handoff。五项桥接变异去掉请求冻结、preflight 拒绝、raw 模式拒绝或尝试/attach 记账。

另一个独立 C 模型从生产 host.c 提取原 regulatory helper 和新的 preflight 全函数体，提供 country/channel/context/recovery/scope 原语：13 组策略案例及国家域动态复查；三项变异绕过监管调用、country 比较或 recovery 拒绝。不是实际监管数据库或驱动并发认证。新 header 纳入真正 WLAN source copy，完整目标构建验证 native API 类型与链接。

上述新检查已通过 bridge-controller，完整 host 回归及目标构建仍在运行。0162 七项必选已 success，diagnostic 尚在运行，无新失败；不记作全门禁完成。公开 init/START 仍关闭，无新手机包或操作。

## 已验证结果

最终测试源码提交 `e08a5ed5fabe258e48d67ee4d6c6a8690f11772c`，Actions 42626922090 的 bridge-controller 作业 129192952378 success。新 request bridge 的八组成功模式、15 类有效字段变化、13 组 native-policy 模型与五项桥接/三项策略变异全部通过；旧 bridge/session/scope/rate/runtime/managed/provider 回归同样通过。

首轮桥接模型已通过，policy 源码占位符替换误匹配输出字符串导致编译失败；已限定替换首次占位符，修正后真实执行 policy 模型与变异。没有使用编译失败冒充变异成功。

完整 host 生命周期、其余原生组合与 WLAN 编译仍未结束，不记作全门禁或实机通过。BSSID/retry/aggregation 依旧只有快照，没有 native 应用成功记录。
