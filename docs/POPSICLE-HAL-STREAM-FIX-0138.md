# 0138 HAL 属性流式枚举修复

手机 0137 backup 在 sc_hals 报 /system/bin/printf: Argument list too long，继而 NO_RUNNING_WIFI_HAL。全部包校验通过；错误位于快照目录创建之前，更未到 Wi-Fi 关闭或模块操作。不是 HAL 不存在的证明，原代码把读取失败错误地表现为空清单。

参考 XAirDrop 891ffe6 的 module/action.sh hal_services() 直接 getprop | sed 流式筛选方式。旧 adapter 先捕获整份 getprop 输出，再交给可能是外部程序的 printf，超过单个 exec 参数大小限制。现改为先流式筛选 HAL 行，同时传递 getprop 退出码回执；只保留少量服务名，用 here-document 交给 sort，不将整份属性表或最终列表作为外部命令参数。

getprop 非零、回执缺失/重复/非法、sed/sort 失败或非法服务名均拒绝；合法空清单与读取错误分开处理。没有改为直接忽略管道错误，也没有把单个 HAL 名称写死。只有 sc_hals 函数改变，其他 IO 函数、主控制器、状态机和两份 raw ELF 均不变。

45 项回归通过，含超过 2 MB 的完整属性表并强制外部 printf，正向验证两个 HAL 名称排序、忽略 stopped/debug_pid 属性，以及读取/过滤/排序错误拒绝。另核对 IO 整文件差异仅 sc_hals；用实际 0137 包模拟已安装状态再覆盖四文件，14 项运行校验均通过。

小包仅 CHECK_FIRST.txt、SHA256SUMS、module.prop、popsicle-stock-cnss-io.sh，5335 字节；不含 ELF、不调用驱动、不触及 boot/init_boot。生成器以 0136 原始保留文件 SHA 为基准，只允许新增 IO helper 及说明/版本变动，所有未列入允许集合的脚本和两份驱动必须保持原字节。

已安装用户不必重装/重启，修复后可直接重新 backup。此前 NO_RUNNING_WIFI_HAL 出现在 mkdir 前，因此不应删除状态目录；若状态不符应保留并检查。完整 0138 包供未来安装使用，仍无自动加载，保留安装/运行期独立清单。当前主机模拟通过，手机修复后 backup 尚待回传，不代表 Android 调用或驱动运行验收。见 [验证 JSON](research/popsicle-hal-stream-fix-0138-validation.json)。

[CI 42288035806](https://github.com/xxz3312/XAirDrop-17/actions/runs/42288035806) 的 policy/package 已通过；下载的小包 artifact 摘要匹配，内层修复 ZIP 与本地验收包字节一致，SHA256 为 4fefcdae475055fedad2f4e8a3474282d4b361b83dd6991360874f7b3af5c2dd。手机修复后结果尚待回传。
