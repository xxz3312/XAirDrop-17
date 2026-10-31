# 0083：原生 MLME 状态机创建与销毁入口

0082 已执行通用引擎，但由适配器直接调用其 create/delete API。本阶段新增模型提取并执行固定 WLAN 源码中的 `mlme_vdev_sm_create` 和 `mlme_vdev_sm_destroy` 原始函数体，以这两个原生入口包围八种启动组合，以及 INIT/0 SSR 保留、初始子状态漂移拒绝用例。

模型检查 VM-id 名称、原始引擎上下文及 INIT 初始状态；创建依次登记 minidump、创建 SM 锁和命令 mutex，销毁依次释放 mutex、SM 锁、移除 minidump，最后实际释放引擎分配。注入分配失败时必须返回失败，不发布 handle 或初始化后续资源。另执行三次成功创建/销毁配对；原生 destroy 不清空父字段，由测试代码在验证释放后显式清空，不能宣称原生接口幂等。

新增两个负对照：遗漏原生引擎释放、掩盖分配失败返回值，均须由专门断言拒绝。原有八种组合及三项引擎/子状态负对照继续执行，0082 独立模型仍单独运行。

Python 语法检查通过，完整 Actions 验收待完成。

本阶段仅增加验证模型与 CI 接线，没有生产功能激活。锁/minidump/内存失败注入仍是平台模型，没有执行真实 QDF 锁、minidump 或并发析构。测试 harness 的引擎销毁不能授权驱动在 runtime/父资源尚存时提前销毁 SM；真实 object-manager 创建/销毁调用方、MLME callback adapter、完整 WMA 后处理和物理 DP/peer 生命周期仍未执行。实际 START/UP 的 SSR 恢复、父资源/停机自动协调和完整 AWDL 收包仍未完成，backend 关闭，无新手机测试包。
