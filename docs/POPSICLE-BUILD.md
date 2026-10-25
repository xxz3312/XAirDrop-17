# 小米 17 诊断构建入口

`tools/kernel/popsicle_trial_build.sh` 是原厂源码基线的实验性 Kbuild 入口，
不是完整 Xiaomi DDK 构建环境，也不生成可安装包。
源码提交和工具链来源见 [版本记录](popsicle-source-lock.json)。

## 输入布局

下例假设此仓库和输入目录并列：

| 目录 | 内容 |
| --- | --- |
| `analysis/17pm-baseline` | 原厂采集包解压内容，包含 `kernel-config.gz` |
| `xiaomi17-common-r62` | 锁定的 ACK R62 common 源码 |
| `xiaomi17-soc` | 锁定的小米 SoC 扩展源码 |
| `xiaomi17-wlan` | 锁定的小米 WLAN 源码 |
| `sm8850-reference-modules` | 版本记录中明确标为参考用途的 OnePlus SM8850 dataipa 源码 |
| `toolchains/clang-r536225` | 官方 Clang 目录，含 `bin/clang` 和 `lib/libclang.so` |
| `toolchains/rust-1.82.0.p2` | 官方 Rust 目录，含 `bin/rustc` |
| `toolchains/host` | Linux 主机构建工具与头文件，按 `usr/bin`、`usr/include` 等布局 |
| `build-popsicle` | 独立诊断输出，不得放在任何输入目录里 |

主机还需 Git、Python 3、make、GCC、gzip、基础开发环境。
`host` 目录中需 flex、bison、m4、bc、bindgen、pahole、libelf/libdw 及头文件。
bindgen 使用版本记录中的官方 **0.69.5**；Ubuntu 24.04 提供的 0.66.1
在本次 Rust 绑定生成中崩溃，不能作为替代版本。
脚本当前面向 Linux x86_64；不应在手机上执行。

## 应用源码编译修复

在本仓库根目录运行，先检查再应用：

```sh
git -C ../xiaomi17-wlan apply --check "$PWD/kernel/patches/popsicle/0001-t2lm-enum-type.patch"
git -C ../xiaomi17-wlan apply --check "$PWD/kernel/patches/popsicle/0002-link-reconfig-prototypes.patch"
git -C ../xiaomi17-wlan apply "$PWD/kernel/patches/popsicle/0001-t2lm-enum-type.patch"
git -C ../xiaomi17-wlan apply "$PWD/kernel/patches/popsicle/0002-link-reconfig-prototypes.patch"
```

第一项把比较常量换成变量所属枚举中的 `WLAN_T2LM_DISABLE`（值仍为 0）；
第二项包含实现函数自己的声明头文件。没有关闭 warnings-as-errors。

## 配置与准备

```sh
bash tools/kernel/popsicle_trial_build.sh prepare \
  ../analysis/17pm-baseline ../xiaomi17-common-r62 ../xiaomi17-soc ../xiaomi17-wlan \
  ../sm8850-reference-modules/vendor/qcom/opensource/dataipa \
  ../toolchains/clang-r536225 ../toolchains/rust-1.82.0.p2 \
  ../toolchains/host ../build-popsicle
```

`configure` 只运行配置；`prepare` 还运行 `modules_prepare`。
每次从原厂配置重新开始，检查编译器与 bindgen 身份、Rust、BTF、KCFI、页大小等关键设置。
若关键设置丢失则停止，全部配置差异保存在输出目录的 `stock-config-delta.json`。
保留关键设置不代表其他 OEM 配置差异可以忽略。

## WLAN 对象编译

将阶段改为 `wlan-object` 会编译 `qca_cld3_peach_v2.o`，默认最多 4 个并行任务，
可通过 `POPSICLE_BUILD_JOBS` 降低。公开 SoC 树缺少 HWID 头文件，因此该阶段
默认会停止。只有验证了与原厂调用者匹配的声明后，才通过
`POPSICLE_HWID_INCLUDE=/path/to/verified/header-directory` 显式提供头文件。
仓库中的最小声明不是完整厂商头文件，也不会由脚本自动选用。

该阶段不运行 modpost，不生成 `.ko`。完整模块还需要真实导出表、
保护符号/模块配置、结构布局、KCFI 和固件验证，不能从导入期望值拼接假的导出表。
不要把对象编译成功解释成 WLAN 已能替换、AWDL 已工作或可刷入。
