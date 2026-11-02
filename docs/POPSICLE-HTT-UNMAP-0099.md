# 0099 Production HTT peer-unmap parser and indication ownership

离线验收完成：[CI 41515796705](https://github.com/xxz3312/XAirDrop-17/actions/runs/41515796705)（`bbe95ed`）两项作业成功。相关生产代码、夹具、边界与失败检查、CI 入口集中完成后统一编译验证。

Patch 0037 adds `dp_htt_t2h_peer_unmap_try_handle()` to the production WLAN
`dp_htt.c`. The existing HTC receive handler invokes it before accessing the
packet context or header. It consumes transport errors, cancellation, absent
context/buffer/data, and short headers. Successful non-unmap messages return to
the existing generic dispatcher with buffer ownership intact. Recognized unmaps
are checked before field access, delivered to the original native DP handler,
and their indication nbuf is freed exactly once after delivery.

V1 requires its four-byte prefix. V2 requires the twenty-byte consumed prefix
through `PEER_WDS_FREE_COUNT`, rather than requiring all twenty-eight bytes of
the current wire format; this preserves the previous consumer's trailing-field
compatibility. A bounded copy into aligned local words uses the original wire
GET macros and original MAC deswizzle. The old two switch arms are removed;
unselected switch arms and the existing HTC receive registration are retained.
Other HTT payload formats are not validated by this change.

The new host fixture executes the exact production helper and the original
MAC deswizzle with an independent literal wire encoder. The 152 prior composite
selections now route modeled indications through this helper, with sixteen extra
v1/v2, aligned/unaligned, tracing/release-timing and MAC-source-branch selections.
303 parser contracts cover all lengths 0..36, both formats, unaligned input,
unknown type ownership, failure/cancel and absent packet/context/buffer/data.
Twelve new mutations target length checks, IDs, MAC/WDS/count fields, delivery,
free, cancellation accounting and borrowed ownership; 56 inherited controls
keep their original modeled unmap path. All checks passed in the accepted run.

The generic dispatcher and HTC/HIF registration/transport are compiled and
source-reviewed, not executed by this host fixture. The BIG_ENDIAN_HOST probe
converts host-word MAC byte representation before calling that original source
branch on a little-endian host; it is not big-endian platform certification.
Initial DP objects/references/maps and peer-gone gate, platform primitives and
cleanup/event/AST/statistics endpoints remain models. Nbuf/DP heap storage is
actually freed on the host under sanitizers. No real firmware delivery,
concurrent producers, automatic parent shutdown, active SSR, phone/RF or AirDrop
validation is claimed. Backend remains disabled.

## 验证记录

168 组释放组合、303 项解析合同、68 项失败控制（56 项继承、12 项新增），0098/0097/0096/0095/0094/0093/0092 七项独立组合、53 项 Python 检查、旧回归、完整 WLAN 编译、CNSS、严格链接、七项选定布局和模块记录检查均通过。首轮夹具缺少提前作用域内的 `QDF_MAC_ADDR_SIZE`；次轮主机组合通过，但完整 WLAN 编译发现日志使用 `%u` 不匹配 `qdf_size_t`。补齐宏、将生产日志改为 `%zu`，并让夹具使用 `size_t` 返回值和 printf 格式检查后，本次完整重跑成功。失败记录保留在验收 JSON。

本轮及七项旧组合生成源码哈希独立重建匹配 CI，本轮 SHA-256 为 `39cec2a527d841ce84467eead9b62d26ff7484ab68f876ab20c21d6a57b060eb`。补丁 0037 从原始 HTT 文件重放结果与 CI 来源一致；generic dispatcher 仅有预期的入口门控、接收错误代码迁移和两项旧 unmap 分支移除，其他分支匹配。原始 deswizzle 函数体、wire enum/宏来源、51 份报告中的生产源码、37 个路径别名、锁定源码清单及两份 ZIP digest 均核对。布局候选对应最终链接 WLAN，五个模块无版本记录不匹配或缺版本依赖，WLAN 无未解决依赖。本地未执行 C 编译。见[完整验收 JSON](research/popsicle-htt-unmap-0099-validation.json)。

本轮确实新增生产 WLAN 解析/所有权代码；实际 HTC/HIF 消息输送、完整 generic dispatcher 的运行和整机兼容性仍未验证。backend 保持关闭，手机无需操作。本阶段不提供可直接安装或已认证的整合包。
