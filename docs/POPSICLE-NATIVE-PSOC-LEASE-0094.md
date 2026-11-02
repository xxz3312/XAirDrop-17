# 0094：原生 PSOC 引用与 PDEV 释放期间的父对象保留

本阶段将六个原生 PSOC get/try/put、PDEV attach/detach 和逻辑删除函数体接入 0093 的堆 PDEV 组合。原生 attach 保存 PDEV ID、映射、计数并取得 PSOC OBJMGR 引用；原生 PDEV 最终 free 通过原生 PSOC detach 清除映射并归还 attachment 引用，随后才销毁 PDEV 锁、关闭 peer 队列和释放 PDEV heap。fixture 调用方另外持有 PSOC HDD 引用，等整段 PDEV 释放完成后才归还。

0093 的 56 个序列均启用该原生 PSOC 合同；另有 16 个额外 PSOC OSIF 引用和两种最后归还顺序的组合，共 72 个序列。peer/PDEV 组件、PSOC 脱离或异步完成失败时检查 PSOC 映射及引用保留。单槽映射合同检查满表 attach 失败和已脱离 ID 的拒绝。容量 1 取自目标 Kbuild 的默认值，不代表完整目标配置或多射频认证。

既有 11 项负对照保留，增加六项 PSOC caller pin、attachment pin/detach put、final put、map ownership 和逻辑删除准入负对照。移除 caller pin 的负对照通过原生 PSOC 最后引用分支进入最终标记端点，要求检测到此时 PDEV heap 仍存活；不以镜像计数替代该顺序检查。

PSOC 存储及最终 destroy/free 仍是静态模型端点，没有执行原生 PSOC create、真实 PSOC 组件或 PSOC heap free。PSOC peer/VDEV attachment 引用、PDEV create/真实组件、真实 DP unmap/完成图和全局迟到生产者未纳入本组合。原生 PSOC attach 本身不检查逻辑删除状态，detach 不核验有效槽位的 owner；本阶段只选择私有、串行化且已核对归属的映射合同，没有修改这些生产行为或实现自动停机协调。backend 关闭，手机无需操作。

CI 与独立验收待完成。
