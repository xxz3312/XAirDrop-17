# 0137 KSU 安装期与运行期完整性校验修复

手机 0136 安装后状态确认原厂 CNSS2/WLAN note 匹配；两份候选 ELF 及其他保留文件 SHA 均 OK，但 customize.sh 缺失导致 BUNDLE_BLOCKED。此前包错误地把安装期脚本列入运行期 SHA256SUMS。

核对 [KernelSU installer.sh](https://github.com/tiann/KernelSU/blob/019a3c0103a8f8d56675546016c4073d0fd18352/userspace/ksud/src/installer.sh#L464)，安装结束明确删除 customize.sh。核对 XAirDrop 891ffe6 的 module/customize.sh，以及 OPAirDrop 28a3a1d 的 module/customize.sh/运行时验证分工后，采用独立安装期/运行期清单。

INSTALL_SHA256SUMS 校验 customize.sh、运行期清单和其他安装文件；SHA256SUMS 仅列安装后保留的运行文件。customize.sh 在安装时先验证两份清单。没有 sha256sum --ignore-missing，没有放宽保留文件的缺失或篡改检查；仍不自动加载、重试或触碰 CNSS2。

41 项测试通过，包括完整安装、KSU 删除安装脚本后运行校验仍通过、控制脚本/驱动缺失或修改仍被拒绝，以及小包不得修改保留 ELF/脚本。用实际新包和原 0136 ZIP 模拟完整安装及已安装旧包覆盖三文件，运行校验均通过。17 条目完整包和仅 1718 字节的小包分别生成；小包只有 CHECK_FIRST.txt、SHA256SUMS、module.prop，没有可执行脚本、驱动或分区写入入口。

小包生成器以原 0136 ZIP 摘要和全部文件 SHA 为固定基准，强制所有保留脚本/驱动摘要不变，另外验证新包内实际文件字节，拒绝其他改动。现有已安装用户只需应用小包，不必重装或重启。未来安装使用完整 0137 包。两份 raw ELF 完全复用 0133，未重编译/strip/修改。

当前仅主机模拟通过，修复后的手机 check 尚未回传，驱动未执行。修复后仍可能出现 LEGACY_STATE_PRESERVED；该结果与本次 customize.sh 问题不同，应保留旧事务后单独核对，不能删除状态继续试验。见 [验证记录](research/popsicle-ksu-checker-fix-0137-validation.json)。

[CI 42285579522](https://github.com/xxz3312/XAirDrop-17/actions/runs/42285579522) 的 policy/package 已通过；下载的小包 artifact 摘要与 GitHub digest 匹配，内层修复 ZIP 与已模拟验收的本地 ZIP 逐字相同，SHA256 为 e36c4150c62c07aadb1012605cf1d9b175acb7292bb097953920c454fae1472f。手机修复后的结果仍待回传。
