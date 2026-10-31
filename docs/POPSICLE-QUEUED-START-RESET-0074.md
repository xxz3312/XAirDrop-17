# 0074：已排队但未执行 START 的显式 SSR 回收

新增一个严格受限的 radio 请求分支：START 已被 MC 队列接受，但回调从未执行，随后由原生 MC 停机 flush。它仍为原生 INIT，未发送 START，也没有取得启动用的 PM/响应定时器资源。已经执行 START 回调、发送 START、等待响应、UP、队列提交失败或非 SSR fence 都继续保留资源。

控制器在关闭准入时只为 pristine NEW、已接受且唯一 pending START、零 users/错误/回复/执行事实的实例记录候选资格。实际 radio flush 释放请求内存、归还 work reservation、减少最后 pending 引用之后，才向 runtime 发布包含 psoc/vdev/owner/controller 精确身份的通知；发布后不再访问控制器。runtime 仅为原始 SSR owner 保存该事实，重复匹配通知记录 sticky completion_error，外来 owner/psoc 忽略。

原生停机窗口据此识别候选，但不会只凭 runtime 标记删除资源。新增 radio check/release 再核对活 registry、私有 flush 事实、回调未执行、未发生 preflight/START/STOP/UP/DOWN、无 users/pending、没有 fence 后回调、原生 INIT 和 untouched transaction。先做全部预检，再同步关闭 NDI 响应定时器，重新核对并 unlink controller，最后释放其 VDEV 引用。之后接续 0072/0073 的 PE → peer → 实际 DP final-free → WMA/legacy → 对象实际 final-free。

radio_requested 保留，BLOCKED/ESHUTDOWN 原值保留；只新增明确的 ssr_cancelled_before_start 记录，不改写成普通 CANCELLED/DOWN，不发送 SM/WMI/STOP/DOWN，不补 PM/固件 ACK。任何中途错误保留剩余资源并设置 sticky recovery_error，不能靠反复重试清除错误。若同步 timer drain 期间出现回调，即使 users 回到零，也不能退休 controller。

新增 Actions C 模型保留 0073/0072 回归，执行生产 runtime/radio、原生 scheduler stop/queue flush、PE 析构和 peer 路径。覆盖 2.4 GHz/5240 MHz、同步/异步 DP、batch、额外 final-free 引用、没有实际 flush 的 MC 观察、13 类 controller/身份/回调拒绝、timer drain 期间回调、重复/外来通知，以及已执行 START/响应/UP、队列失败、非 SSR fence。负对照删掉私有 controller flush 检查后，必须被“runtime 有标记但私有事实缺失”的用例发现。

本地 53 项 Python 检查通过，C 模型、完整编译、严格链接和七项选定布局检查待 CI。新增入口编译进原 WLAN，公开 Wonder ops/priv ABI 不变，没有自动资源释放 caller，也不启用 backend 或制作手机测试包。

QDF/锁/定时器/完整 scheduler、MLME SM dispatch、PE 分配及其余 cleanup primitives、DP/peer 物理析构和父资源仍含模型。显式 caller 必须在合格 SSR 窗口中保持原始父资源并串行所有 poll/teardown。这不是原生自动停机/父资源租约，不支持实际 START/UP 回收，不证明驱动加载、固件/空口或 AirDrop。手机无需操作。
