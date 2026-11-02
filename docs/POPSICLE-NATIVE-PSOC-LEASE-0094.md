# 0094：原生 PSOC 引用与 PDEV 释放期间的父对象保留

本阶段将六个原生 PSOC get/try/put、PDEV attach/detach 和逻辑删除函数体接入 0093 的堆 PDEV 组合。原生 attach 保存 PDEV ID、映射、计数并取得 PSOC OBJMGR 引用；原生 PDEV 最终 free 通过原生 PSOC detach 清除映射并归还 attachment 引用，随后才销毁 PDEV 锁、关闭 peer 队列和释放 PDEV heap。fixture 调用方另外持有 PSOC HDD 引用，等整段 PDEV 释放完成后才归还。

0093 的 56 个序列均启用该原生 PSOC 合同；另有 16 个额外 PSOC OSIF 引用和两种最后归还顺序的组合，共 72 个序列。peer/PDEV 组件、PSOC 脱离或异步完成失败时检查 PSOC 映射及引用保留。单槽映射合同检查满表 attach 失败和已脱离 ID 的拒绝。容量 1 取自目标 Kbuild 的默认值，不代表完整目标配置或多射频认证。

既有 11 项负对照保留，增加六项 PSOC caller pin、attachment pin/detach put、final put、map ownership 和逻辑删除准入负对照。移除 caller pin 的负对照通过原生 PSOC 最后引用分支进入最终标记端点，要求检测到此时 PDEV heap 仍存活；不以镜像计数替代该顺序检查。

PSOC 存储及最终 destroy/free 仍是静态模型端点，没有执行原生 PSOC create、真实 PSOC 组件或 PSOC heap free。PSOC peer/VDEV attachment 引用、PDEV create/真实组件、真实 DP unmap/完成图和全局迟到生产者未纳入本组合。原生 PSOC attach 本身不检查逻辑删除状态，detach 不核验有效槽位的 owner；本阶段只选择私有、串行化且已核对归属的映射合同，没有修改这些生产行为或实现自动停机协调。backend 关闭，手机无需操作。

离线验收完成：[CI 41424409521](https://github.com/xxz3312/XAirDrop-17/actions/runs/41424409521)（`1d8aec3`）两项作业均成功。72 个组合序列、17 项负对照、0093/0092 独立组合、53 项 Python 检查、0091/0090 及旧回归、完整 WLAN 编译、CNSS 检查、严格链接、七项选定布局及模块记录检查均通过。

独立重建的新组合源码 SHA-256 为 `aafe7141a46328a800ceaf9e9c680bbab4d3e302839cc0cff072e1c4b6110b2b`，与 CI 相同；六个原生 PSOC 函数体、PSOC 原始文件和 Git blob 身份，以及此前 10 个原生 PDEV 函数体已逐项核对。0093/0092 独立组合的生成源码也匹配。46 份报告中的生产源码与仓库一致，核对 37 个路径别名，固定源码清单匹配；两份验证 ZIP digest 与 Actions 一致。布局候选对应最终链接 WLAN，五个模块无版本记录不匹配或缺版本依赖，WLAN 无未解决依赖。本地未执行 C 编译。见[验证记录](research/popsicle-native-psoc-lease-0094-validation.json)。

负对照验证的是原生 PSOC release 的减零分支进入模型析构端点时 PDEV 仍存活；没有执行真实 PSOC dispatcher/free，也不据此宣称已复现内核 UAF。本组合的 PSOC 逻辑删除仅模拟私有父资源整体停机；真实共享 PSOC 的关闭准入和真实组件关闭仍需生产调用方单独协调。下一步仍需原生 PSOC 最终析构、真实组件/DP 完成图及生产父资源协调。
