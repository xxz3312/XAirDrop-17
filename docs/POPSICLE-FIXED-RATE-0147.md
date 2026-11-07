# 0147：固定速率原生命令执行器

0146 的 Actions 42365788018 全部八项必选作业通过，包含 host 监管行为及七项变异控制、完整 WLAN 编译、严格链接和布局检查。本轮新增一个内部固定速率执行器，公开 init/poll 和速率接口仍关闭，手机无需操作。

## 上游依据和差异

- Weverses/OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d`，`kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch`，blob `8874b020b4d7eadea41adea787d53dcca08a3c62`：本轮重新读取 preamble 转换和 fixed-rate/GI/chwidth 顺序。复用 `hdd_assemble_rate_code`、NSS 减一及相同 GI 编码，使用原生 `wma_cli_set_command`。
- Leekin2/XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb`，`module/action.sh`，blob `024cd17fb19c50c10f204552f8a2cd6fffc5d30a`：本轮重新读取手动入口和支持范围；不改加载脚本、不替换原厂 CNSS2、不生成手机操作包。
- MiCode WLAN `36df473046706a5259942e1bf7222108dbbb860f`：核对 `wlan_hdd_main.c/.h` 的编码包装、`wlan_mlme_ucfg_api.h` 的原生编码入口及 `wma_api.h` 的命令接口。本轮没有重写硬件编码格式。

上游固定速率函数在出错后仍继续提交，后续返回值可覆盖前面的错误。本项目保留首次错误并停止提交剩余命令，以免把部分应用误记为成功。上游 LEGACY 默认映射 CCK，公共请求无法明确区分 OFDM，本轮保守拒绝 LEGACY。上游 mask setter 本身返回错误，本轮也不实现或宣称自适应速率支持。

## 执行和所有权合同

- 输入仅限 HT20、1..2 NSS。HT/VHT 的 MCS 上限为 7/9，GI 仅 DEFAULT/SHORT；HE/EHT 的 MCS 上限为 11/13，GI 仅 DEFAULT/0.8/1.6/3.2。此为当前执行器的支持子集，不是完整 PHY 标准或实际平台能力清单。MCS14/15、宽带宽等请求拒绝，不静默截断。
- 要求被引用的 PASSTHRU VDEV，精确匹配 MLME 回指、NDI 类型、零 subtype 和已存在的 legacy context。上述形状不能证明固件 CREATE 已确认；实际创建所有权、当前监管信道/NSS/PHY 支持和完整父级存活仍由未来 caller 建立。
- 仅内部函数，没有 managed/runtime/public 自动调用。caller 必须独占序列化 receipt、VDEV/配置和 teardown，并在整个调用及同步回调期间持有 VDEV/组件/父级/固件/WLAN text 的有效生命周期。receipt 不提供租约。
- 新创建的固件 VDEV 使用全零新 receipt。每条命令调用前设置 attempted bit，成功入队后设置 submitted bit，首次尝试前就封闭重入；同步重入返回 EINPROGRESS。
- 任一返回错误可能已有命令逃逸，保留 attempted/submitted 及 first_error，后续调用返回原始错误，不重发、不回滚、不释放资源。完整提交后重复调用返回 EALREADY。没有重置/重试 API，不允许靠清零 receipt 在旧 VDEV 上重放。
- complete 仅指三条命令均入队，绝非固件 ACK、速率已经生效、射频或 Apple 互通。后续整合必须把部分提交纳入合格的 VDEV 停止/删除路径；本轮未把它连接到 START。

## 验证

本地 100 项 Python 回归、Python 语法和 diff 检查通过。独立 fixture 编译并执行实际生产 C，原生 VDEV/MLME、rate encoder 和 WMA 队列为模型：覆盖 HT/VHT/HE/EHT、两种 NSS、有效 GI、MCS 零值/边界以及每一条命令的失败，192 个成功/提交失败组合；另覆盖 14 项参数拒绝、额外 HT GI 拒绝、六项父级形状拒绝、NULL、原请求不变、同步重入、成功及失败重放阻断。

六项变异控制分别禁用重放门禁、吞掉提交错误、改错 GI、错用 NSS、错发带宽、提前记录成功位，均必须编译成功并触发行为断言。ASan/UBSan 本地通过；宿主 ptrace 环境下关闭 LeakSanitizer，Actions 开启。无堆分配。

新增 Kbuild 补丁 0065 及 CI 源码复制入口，已对本地已打补丁的目标 Kbuild 执行 apply --check。桥接 CI 接入该 fixture 和报告上传。本次完整目标构建、真实 native 类型/宏解析和链接仍以新 Actions 为准；下一步继续配置事务与父级生命周期接入，公开启动保持关闭。
