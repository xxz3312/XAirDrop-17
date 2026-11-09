# 0165 重试次数一次性执行器

参考版本：Weverses/OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` 的 `kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch`；Leekin2/XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb` 的 `module/action.sh`。后者仍为驱动替换/服务脚本，没有独立重试提交协议。本阶段不改部署路径，保留原厂 CNSS2。

本机 pinned WLAN `36df473046706a5259942e1bf7222108dbbb860f`：`sme_set_vdev_sw_retry` 直接调用 `wma_set_vdev_sw_retry_th`，后者对四个 AC 逐个调用 `wma_set_sw_retry_by_qos`，无第二层 scheduler。零值跳过全部 AC；中途失败立即返回，已经接受的前缀不能撤回。复用该原生调用链，新增私有 receipt，而非复制 WMI 打包实现。

`mishare_retry_submit_mc` 验证 exact PSOC、WMA interface/VDEV、有界 ID、native valid、PAS opmode、NDI MLME/type/subtype/ext。拒绝阶段 receipt 不变。准入后保存两个 u8 参数，busy 拒绝重入、attempted 拒绝再次执行。data→AGGR、mgmt→NONAGGR 顺序与上游相同。attempted/submitted/skipped 掩码只表示两次组调用，失败组可能已有部分 AC 提交；complete 表示原生提交全部返回成功或跳过，不表示 ACK，也不宣称 mgmt 字段只影响管理帧。所有 u8 值均传递，不另造固件支持上限。

调用者必须串行运行在 MC，持有 exact VDEV/MLME/WMA、父级、固件和代码寿命及 runtime work reservation。本阶段没有自动调用者、post/flush/completion 接线或退出放行机制；不可直接从公开 init 使用。下一步应接入已有 work 预留与完成发布合同，并验证部分失败后的普通退出和 SSR 保留，再接到 request bridge。aggregation、完整父级 lease、公开 START 与 Apple 发现/握手/互传均未在本阶段完成。

测试：新增 fixture 编译实际 production executor、pinned SME wrapper 和 WMA 四 AC 循环，仅底层 per-AC WMI send 为模型，涵盖零值、1/15/255、每个发送位置失败、重入、重放、十五项准入拒绝和六项行为变异。仅 Actions 编译运行，不将模型当作固件或手机证明。本地 100 项 Python 回归、py_compile、fixture 源码生成及 diff 检查通过；目标编译和该 fixture 尚待 Actions。

0164 Actions [42630346131](https://github.com/xxz3312/XAirDrop-17/actions/runs/42630346131) 的八项必需任务已全部 success；optional ICNSS skipped 符合原厂 CNSS2 目标。包含完整 diagnostic 编译/严格链接/布局和记录检查；仍不是实机认证。
