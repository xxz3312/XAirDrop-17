# 0066：Wonder异步启动与回收契约

0065的host会话推进会返回EINPROGRESS；现有Wonder只认识DOWN/UP，且停止回调返回void。直接把两者拼起来，会把异步启动当作普通失败，并把尚未回收的会话标为DOWN。必须先让Wonder入口正确保留资源归属。

## 实际修改

在Wonder内部增加显式managed companion，不改变上游wondertap_ops、wondertap_priv布局或版本号。绑定要求匹配当前ops、提供模块owner、poll_start和retire函数。绑定保持回调模块引用；有资源的实例保持Wonder模块引用。模块引用只保护代码，不保护HDD/psoc或实例内存。

- 首次init只提交一次。EINPROGRESS且有句柄进入STARTING，后续init调用poll_start，保留原MAC和初始化配置，不重发CREATE。
- 部分失败仍有句柄时进入DRAINING，不允许新init覆盖。没有句柄的明确失败返回DOWN并释放实例引用。
- retire只在返回0且句柄已清空时确认DOWN。EINPROGRESS保留句柄和引用；失败、虚假成功或指针改变进入BLOCKED，禁止继续调用可能无效的句柄。
- 原有void deinit在managed模式只发起一次retire，不再无条件置DOWN；后续回收须显式调用有返回值的wondertap_retire。
- STARTING/DRAINING/BLOCKED期间禁止改频道、速率、国家码和BSSID，能力查询也不访问隔离句柄。
- 活动managed实例使用自己的回调，避免全局ops解绑/替换后把旧句柄交给新回调。尚有资源或处于隔离状态时拒绝managed unbind。

未启用managed的同步provider和external monitor保留原有行为。

## 严格边界

**本轮没有安装managed绑定调用方，也没有启用专用无线会话。** 0065 host与0066 Wonder之间的native glue、父资源租约、异步轮询/超时、SSR/remove前回收、组件解绑和实例释放顺序仍需实现。调用方必须在实例/父资源销毁前完成retire和unbind；EBUSY或模块引用不能替代这一条件。当前禁止将新内部绑定入口接到默认provider，不能把本轮称为完整Wonder后端完成。

完整monitor packet DMA、辅助monitor、地址过滤与native RAW仍未接通。没有新手机操作，不要求重跑0064，不提供仅更新版本号的测试包。

## 验证

新增fixture逐字节复制并编译完整生产wondertap.c和对应头文件，以模块引用、互斥锁和vendor回调模型执行真实init/poll/deinit/retire/config入口。覆盖异步顺序、MAC稳定、配置冻结、部分失败、正常回收、全局ops替换、错误指针/虚假成功隔离、模块拒绝与同步legacy/external兼容。ASan/UBSan只验证这些模型，不认证内核并发、父资源、固件或空口。
