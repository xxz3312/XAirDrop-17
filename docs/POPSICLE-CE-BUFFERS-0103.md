# 0103 Native residual CE RX/TX cleanup

Implementation prepared; unified Actions validation pending.

The two original per-pipe cleanup bodies execute in 72 standalone selections and 16 CE-stop integrations after the controlled producer join. RX covers unused/unstarted/device-missing, direct-link ownership, empty and NULL descriptors, and unmap-before-free. TX covers sendlist sentinels, optional callbacks, unused/unstarted/empty queues and the HTT-owned endpoint early return that preserves later queued entries. Six new mutations extend 110 inherited independent controls to 116.

CE revoke/cancel rings, DMA unmap, direct-link pages and TX completion remain models. Host payloads are freed through checked model ownership; retained HTT/no-callback buffers are explicitly released by their model owner after assertions. Native HTT send completion, actual DMA/rings, physical HTT release and production parent shutdown are not certified. No new production patch; backend stays disabled and no phone action is required.
