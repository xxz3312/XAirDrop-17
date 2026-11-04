# 0103 Native residual CE RX/TX cleanup

离线验收完成：[CI 41782619036](https://github.com/xxz3312/XAirDrop-17/actions/runs/41782619036)（`af57774`）六项作业成功。

The two original per-pipe cleanup bodies execute in 72 standalone selections and 16 CE-stop integrations after the controlled producer join. RX covers unused/unstarted/device-missing, direct-link ownership, empty and NULL descriptors, and unmap-before-free. TX covers sendlist sentinels, optional callbacks, unused/unstarted/empty queues and the HTT-owned endpoint early return that preserves later queued entries. Six new mutations extend 110 inherited independent controls to 116.

CE revoke/cancel rings, DMA unmap, direct-link pages and TX completion remain models. Host payloads are freed through checked model ownership; retained HTT/no-callback buffers are explicitly released by their model owner after assertions. Native HTT send completion, actual DMA/rings, physical HTT release and production parent shutdown are not certified. No new production patch; backend stays disabled and no phone action is required.

## 验证记录

0103 已完成离线验收：[CI 41782619036](https://github.com/xxz3312/XAirDrop-17/actions/runs/41782619036)（`af57774`）六项作业成功。88 项残留缓冲区检查（72 项独立、16 项停止链集成）、116 项失败控制及全部旧组合通过；53 项 Python 检查、完整 WLAN 编译、CNSS、严格链接、七项布局及模块记录检查通过。十二份组合源码、两个原生清理函数、55 份报告中的生产源码、37 个路径别名及六份验证 ZIP 摘要均已核对。

原生 RX/TX 清理函数通过模型 CE 撤销/取消队列执行；DMA unmap、direct-link pages 和 TX completion 仍为模型。HTT/无回调缓冲区按原路径保留归属，断言完成后由模型所有者清理。HTT 控制包在真实流程中可能已由其他路径释放；夹具使用活体宿主缓冲区记录归属，未重放此前释放历史。真实环/DMA、原生 HTT TX completion、物理 HTT free 和生产父资源停机协调仍待继续。backend 保持关闭，手机无需操作。

见[完整验收记录](research/popsicle-ce-buffers-0103-validation.json)。
