# 0131：三模块部署准备、手动替换和回退流程

新增独立的三模块运行时工具，不沿用旧的两模块 WLAN 试用脚本。旧脚本遇到 checked CNSS2 配对包或已加载的 checked WLAN 会在 Wi-Fi/HAL 操作前拒绝执行。新工具不改写模块文件、vermagic、CRC、分区或启动配置，也不自动加载任何模块。

打包器只接受 0130 已验收的原始三个 ELF。候选 vermagic 的构建标识与原厂不同，因此必须逐字匹配验收 ELF，并保留已记录的原厂加载器规则依据；不把它误计为原厂字符串完全相同，也不修改头部。导入/导出记录和模块 SHA、来源、runtime 未认证状态一同放入包中。

| 命令 | 行为 |
|---|---|
| status | 只读输出系统/内核、槽位、boot 哈希、已加载模块原始 build-id note 哈希、refcnt/holders 和事务阶段；单独脚本也能运行 |
| check（默认） | 只读核对私有目录权限、包内哈希、设备/固件、当前槽位原厂 boot 哈希、模块身份和依赖；不创建事务或停止服务 |
| backup | 核对原厂栈后，只复制两份原厂模块和记录 Wi-Fi/HAL、boot-id、清单身份；不改变模块或网络 |
| apply | 显式手动运行时替换；先保存并同步备份，关闭 Wi-Fi/HAL，普通删除原厂 WLAN/CNSS2，再加载 provider→CNSS2→WLAN |
| restore | 只接受同一 boot-id、同一包的健康 ACTIVE 事务；先成功完成 live-unload，确认无 holders/引用，再删除 WLAN→CNSS2→provider，加载备份 CNSS2→WLAN |
| archive | 只允许重启之后、当前已核对为原厂栈时归档旧事务；保留其内容，不重放旧动作 |

目标锁定已捕获的 popsicle、OS4.0.5.0.XPBCNXM、6.12.69-android16-6-4k，原厂模块的完整 SHA 和原始 GNU note 字节哈希均已记录。缺失 build-id note、未知 boot、额外 holders、旧试用状态、常见 AP/副 WLAN 接口或任何身份不匹配都会阻断。check 是当时的只读观察，apply/restore 在锁内重新核对，不复用旧的检查结论。

包须由 root 解压到 `/data/adb/` 的独占子目录，文件不得是符号链接或允许组/其他用户写入。命令工具使用固定系统 PATH。元数据和备份保存于 `/data/adb/xairdrop17-pair-transaction`；新旧工具共用 `/dev/` 下的 WLAN 锁，避免并行替换。临时锁随重启消失，持久事务通过 boot-id 拒绝跨重启重放。

每个有副作用的步骤先同步 `intent` 阶段，再执行命令，再记录结果。信号中断、记录失败或命令失败后立即停止。命令返回非零不被解释为“肯定没有效果”，因此没有自动 rmmod/insmod 回滚、强制卸载、引用清零或失败重试。失败时保留现场；下一次启动仍使用未修改的原厂文件，Wi-Fi 用户开关可能需重新打开。只有完整、健康的已知 ACTIVE 事务可以走显式热恢复。

模块字节不重新签名或剥离调试信息，私有 action/raw/mgmt 后端保持编译默认关闭。`acceptance.json`、清单和 SHA256SUMS 跟随包一起提供。包不是 Magisk/KernelSU 安装器，也不带开机自启。

首次手机操作应仅做只读采集。例如在解压后先运行 `sh /data/adb/<包目录>/popsicle-pairctl.sh status` 和 `check`，核对身份后再安排实际运行时试验。本阶段未对手机执行 apply、restore 或任何模块命令。

86 项本地回归和 shell 语法检查通过。测试实际执行策略核心与建包验证器，模拟 Android IO，覆盖 9 个 apply、10 个 restore 副作用点各自失败、9 个 intent 写入失败，以及错误身份/额外 holders/损坏备份/中断事务/重复清单字段/候选头部变化等拒绝路径。失败模型在返回非零之前先改变模拟状态，验证不会继续运行或自动回退；这些模型不等于内核或 Android 命令已经实测。

[部署准备工作流 42252554356](https://github.com/xxz3312/XAirDrop-17/actions/runs/42252554356) 的 tests/prepare 两个作业已通过。下载后核对了外层 artifact ZIP 摘要、内层试验包摘要、9 个包内文件及所有 SHA256SUMS；三份模块与 0130 完全一致，两个脚本与部署源码完全一致，boot/原厂 note 清单和验收 JSON 一致。内层包大小为 170771976 字节，SHA256 为 `b7fe3645c7c464269958c3fdb8879685c76cd427f5af429295efec811309acda`。包由该工作流固定取用已验收的 0130 产物生成，没有重新编译或修改模块。

CI 与包内容校验结果见 [0131 机器记录](research/popsicle-pair-deployment-0131-validation.json)。复用的内核验收见 [0130](POPSICLE-LIVE-UNLOAD-0130.md)。本阶段完成部署工具和可复现手动试验包；原厂实际加载器、sysfs/文件排空、平台退出/重载、完整 private ABI/KCFI、RF 和 Apple 互传仍需实机验收。
