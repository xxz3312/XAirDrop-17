# 0166 重试配置批量接线

本批遵从用户要求，一起完成相关实现后集中运行一轮 CI，避免每个小环节单独构建。

## 上游与本机依据

重新核对 Weverses/OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` 的 `kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch`：data→AGGR、mgmt→NONAGGR。Leekin2/XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb` 的 `module/action.sh` 没有独立重试配置或完成协议，仍提供驱动部署参考。保留原厂 CNSS2，本批不改手机部署。

## 一批完成的接线

1. `mishare_retry_post` 冻结两个标量，获取 VDEV 引用和 runtime work 预留后发布 MC 消息。进入检查成功才执行原生提交；flush 只发布取消。完成时先释放 request，再在预留和引用仍持有期间发布 receipt，最后 work_put 和 release_ref。预发布失败无完成回调，允许内联完成。
2. runtime registry 提供 begin/posted/complete。先锁定 requested 防止重放，验证速率已成功、PE/channel 就绪且无前一批工作、无线 START 或退出请求。记录队列返回与实际完成，分别处理内联时序。receipt 按原始参数校验零值 skip、组顺序、失败前缀、ID、busy 和错误；重复/矛盾完成隔离。
3. 新 host retry poll 与 request bridge 接线。完成速率准备后才提交重试；返回 EINPROGRESS 的提交与完成轮询分开。完整请求保持原来的冻结语义，重试参数改值被拒绝。0 只表示内部子集提交完成。
4. 普通退出必须等待 posted、completed 与 work 释放，再沿原 PE/peer/VDEV/DP 回调退出；部分重试失败不触发重放，不改写失败记录。重试选定后的 SSR 暂返回 EUCLEAN 保留 owner/父级，不继承仅针对速率验证的 SSR/tail 放行。此保留包括未执行的 flush/预发布失败，后续可单独收窄。

## 验证范围

100 项本地 Python 回归、py_compile、组合源码生成和 0065→0069 Kbuild 顺序检查通过。没有本地原生编译。

新增工作包装测试覆盖预发布分配/引用/预留/排队失败、正常完成、flush、关闭、提交失败、内联及参数快照，含五项行为变异。组合 fixture 覆盖 704 组参数/失败/内联/原生普通退出组合及七项发布/取消/SSR/重复完成场景，含三项行为变异。实际 production runtime、prestart、retry work/configure 与选定原生退出代码共同运行；host poll 使用从原函数提取的状态处理尾段，身份门禁在完整 host fixture 编译覆盖；底层 retry WMI executor 是模型，另由 0165 原生 SME/WMA 循环测试验证。request bridge 模型新增重试等待、冻结值来源、失败保留/不可重放场景。以上新增原生执行结果待集中 CI，数量不是已通过声明。

0165 Actions [42652443620](https://github.com/xxz3312/XAirDrop-17/actions/runs/42652443620) 八项必需任务已全部 success，含重试原生组提交、目标 WLAN 编译与严格链接。

## 尚未完成

aggregation 的原生应用、重试后的 SSR 合格回收、跨轮询自动父级 lease、完整公开初始化和 START 仍关闭。没有新的手机安装包，没有 firmware ACK、射频、Apple 发现/握手/双向互传证明；手机无需操作。
