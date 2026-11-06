# 0132：手机检查器权限与运行内核版本修复

用户首次只读结果确认机型与固件匹配，活动 boot SHA 及两份原厂模块的 GNU build-id note 与审计记录一致。当前 CNSS2 为 live，唯一 holder 是 qca_cld3_peach_v2；WLAN 为 live、refcnt 为零、无 holder。这是身份和引用关系观察，不是 private ABI、加载/卸载或无线运行验收。

跟踪日志显示目录 root 归属正确、权限为 700，但 `$((0$mode & 022))` 得到 20，在包校验前返回失败。该算术写法不能依赖 Android Shell 的前导零解析规则。新版本直接检查八进制权限文本的组/其他位，拒绝带写位的 2/3/6/7，保留 root、symlink、格式及目录保护检查，不修改手机目录为更宽权限。

同时修复已知的版本字段误用：模块 vermagic 的短 release 不等同于完整 uname。清单现在精确使用手机观测的 `6.12.69-android16-6-g43b5ab7e247d-abogki558343811-4k`。活动 boot/固件/模块 note、候选 ELF 验收及原厂加载器记录仍逐项核对；不删减版本字符串、不使用通配或跳过 boot 规则。

增加具体阻断输出，包括目录归属、可写权限、缺失文件、运行版本、holder、已加载 note 和原厂文件路径/哈希。更正后的 check 仍为只读。

[工作流 42259977562](https://github.com/xxz3312/XAirDrop-17/actions/runs/42259977562) 的 tests 和 prepare 作业通过。92 项回归覆盖全部 512 种三位权限和 1700/1755/1777/4755，以及非 root、链接、非法模式、完整 uname 生成规则、小包不得修改保留模块或其他身份等合同。手机 Shell 上修复后的执行结果尚未回传，不能将主机测试算作手机检查已通过。

Artifacts 中的 `popsicle-checker-fix-0132-42259977562` 只有三个文件：popsicle-pairctl.sh、deployment.tsv、SHA256SUMS，ZIP 共 5469 字节，SHA256 为 `9d0def8a2ef319aa17f2cd12d8aa4bfddb6ddff7e20786eed6b90ce49fb6482d`。下载后已核对脚本源码、清单唯一变更字段与全部保留文件摘要；将三个文件覆盖到已验收的原 0131 包后，八项完整校验均匹配。驱动、策略核心、验收 JSON 和原 README 不变，没有 `.ko`、分区写入或自动执行入口。

将小包以 root 解压覆盖 `/data/adb/xairdrop17-pair-0131` 后，重新执行 check 并保存日志即可。无需重新下载三份模块；不应直接改旧校验表或跳过检查。手机尚未执行驱动替换，apply/restore 仍不应作为此次修复操作的一部分。

机器记录及上传日志摘要见 [0132 验证数据](research/popsicle-checker-fix-0132-validation.json)。
