# 0130：外部一次性卸载控制器与引用释放

补丁 0064 把 0129 的完整卸载结果接入外部 provider 控制器。成功的非 resident WLAN 模块初始化注册控制器，并增加独立模块引用；原有 PLD 加载引用继续保留。控制器复制 owner 与 typed callback，确认模块已结束 COMING 后才允许进入 WLAN。

| 状态/事件 | 处理 |
|---|---|
| 未注册 | 请求返回 ENODEV，不调用 WLAN |
| 初始化尚未结束 | EAGAIN，保留准入状态，不关闭执行入口 |
| 执行回调繁忙、已关闭或存在注销 scope | EBUSY，不进入 WLAN，不释放引用 |
| 请求获准 | 关闭 execution 准入，状态置 RUNNING；释放控制器锁后调用 WLAN |
| WLAN 或剩余注册状态验证失败 | 保存原错误进入 FAILED，保留引用；后续请求只返回该错误，不重放 |
| 完整卸载成功且执行注册表为空 | WLAN 已返回后清除 callback/owner，置 COMPLETE，再从 provider 释放其独立引用 |
| 完成后的重复请求 | EALREADY，无第二次卸载 |

WLAN 的加载和模式入口使用生命周期互斥锁。首次加载开始后不再接受第二次加载或模式切换；控制器回调使用同一锁。checked 实验分支关闭原有软加载/软卸载路径，避免绕开控制器。初始化参数在首次加载之前仍可经过原 setter 配置。其他编译分支保留原生核心逻辑；checked 编译明确拒绝 built-in / resident 生命周期。

WLAN 的完整卸载返回零后，先在 provider 引用仍持有时释放 PLD 加载引用，再标记卸载完成。只有外层 provider 确认 WLAN 回调已返回且注册表为空，才释放最后一份控制器引用。module-exit 随后的原有 void 卸载调用由入口门禁跳过，避免重复销毁；原生 p2phc_cleanup 仍留给 module-exit 执行。失败的半清理状态保留引用，不能通过此控制器复位或重试。

| 正常成功路径 | WLAN 引用（不含加载器/其他合法调用者的临时引用） |
|---|---:|
| 完成加载，尚未 arm | PLD 1 |
| arm 成功 | PLD 1 + provider 1 |
| checked 注销 scope 内 | PLD 1 + provider 1 + scope 1 |
| checked 注销 scope 成功结束 | PLD 1 + provider 1 |
| 完整 HDD 清理后释放 PLD 引用 | provider 1 |
| WLAN 回调返回，provider 验证成功后 | 0，可再由正常模块加载器执行删除 |

provider 新增两个显式 v1 导出，旧 v2/v3 描述符布局不变。另增加 provider 所有的 0200 写入口 `mishare_live_unload`，只接受显式值 1；默认不自动提交请求。此控制器在同一 provider 生命周期中不重新 arm；后续安装/替换必须协调重建匹配的 provider 生命周期，不能只重载 WLAN。没有 checked WLAN 注册时该入口返回 ENODEV。该入口属于实验控制接口，本阶段未在手机执行。

旧夹具继续独立执行未改变的原生核心，通过只去除有边界的控制器包装恢复函数名；新增联合夹具执行真实包装、模块初始化 arm、外部 provider 和完整原生 HDD 卸载。测试额外增加一个带标记的 WLAN 返回帧，确认提前释放引用会触发错误注入断言。加载、driver sync、平台注销和组件原语仍为模型；真实 CNSS2 注销由独立夹具覆盖。

本地 63 项 Python 回归、独立补丁精确正反和包装移除后整份主文件一致性检查通过。[Actions 42242503130](https://github.com/xxz3312/XAirDrop-17/actions/runs/42242503130) 的 stop-admission 作业通过：联合测试的 9 个隔离场景、1 个并发请求场景和 6 项错误注入，以及原有九套回归全部通过 ASan/UBSan/leak detection。十套源码重新组装及原生/生产/头文件摘要与下载产物一致。

[真实配对构建 42242503014](https://github.com/xxz3312/XAirDrop-17/actions/runs/42242503014) 已成功，下载后再次独立核对：

| 检查 | 实际结果 |
|---|---|
| CNSS2 兼容记录 | 原厂 81/81 导出 CRC、许可证类别、命名空间及入口前置字匹配；仅两个既有 checked 扩展 |
| provider 私有接口 | 0129 的全部 20 项导出记录不变；新增两个 live 接口，合计 22 项，其中 execution/live 门禁 19 项 |
| 实际模块导入 | provider 15、CNSS2 364、WLAN 602 项匹配；WLAN 强导入 arm 且 CRC 匹配 |
| 已知回调入口类型 | WLAN checked callback 与 provider 的 int(void) 请求函数入口前置字一致；四个 PCIe 入口与原厂槽位函数匹配 |
| 参数接线 | provider 控制参数权限 0200，owner 指向 provider 的 __this_module，ops/setter 重定位正确；WLAN load_error 参数仍为 0444 |
| 下载产物 | 完整/紧凑 ZIP、三模块 SHA256 与全部捕获的 type-inputs 一致 |

入口类型字只覆盖已列出的入口，不认证所有间接调用或完整 private ABI。候选 GKI 的 kernel/params.c 已核对其 per-module 参数锁与 sysfs 组移除后释放属性的源码约定，未作为原厂手机运行验收。默认完整诊断工作流仍另行运行。机器证据见 [0130 验收记录](research/popsicle-live-unload-0130-validation.json)。

本阶段完成源码层面的外部控制器接入，不等于原厂手机正常卸载已验收。内核 sysfs 活跃引用/文件操作排空、实际加载器退出、物理 remove 与电源/恢复协调、完整 private ABI/KCFI、部署替换/回退和实机 RF 仍需验收。手机未操作，Apple 发现、握手和双向传输仍未实机验收。
