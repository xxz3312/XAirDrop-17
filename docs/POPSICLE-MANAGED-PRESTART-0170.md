# 0170 内部完整请求的进程上下文准备控制器

## 参考与检查结论

重新检查 Weverses/OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` 的 `kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch`，以及 Leekin2/XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb` 的 `module/action.sh`。上游初始化/模块恢复为适配依据，但没有本项目的异步 request bridge/owner 账本。继续保留原厂 CNSS2，未增加部署或公开 Wonder init 调用。

现有 host 已持有 device、PSOC、PDEV 分配引用，instance 也持有 device 和模块代码引用。它们不能代替跨异步轮询的 HDD 组件/固件可用性合同。原生单次 scope 保护一轮调用，仍要求内部调用者在整个异步阶段保留并协调父级生命周期。本阶段没有宣称完成该长期 lease。

## 一批完成的接线

新增内部 `mishare_wonder_managed_prestart_step(handle)`，只从已 managed_prepare 的完整规范请求推进。进入实例注册表 claim 后检查关闭和已准备状态，然后获取原 native psoc transition、等待 operations、trylock RTNL、重新解析 HDD。通过上下文检查后调用真实 request bridge，返回前先释放 scope，再释放实例 busy。入口没有外部参数替换已冻结请求。

instance 中原 raw bridge 替换为 `request_bridge.bridge`。raw step、完整请求、process retire、idle handoff 和退休轮询始终使用这一个 authoritative owner；没有复制 bridge 或在两个控制器间切换 host 指针。独立的 request metadata 用于初始 prepared intent 和 bound snapshot 互相校验。typed 路径绑定之后不能改值或退回 raw shortcut；prepare 在已尝试创建后仍拒绝修改。

scope 拒绝/上下文失败不新建 owner；部分 host 创建、runtime attach、BSSID/rate/retry 失败保留原 owner，沿原 managed_retire/retire_process 退出。busy 实例不进入 native scope；关闭实例只允许原退休流程。0 仅表示已实现的 prestart 子集提交就绪，不是完整初始化、radio UP 或数据通路可用。公开 callbacks 不调用此 API。

## 本批验证

request bridge fixture 编译从 production 提取的 managed coordinator，与真实 request bridge 组合，新增八组成功参数、九类边界（busy、无请求、closing、scope 拒绝、HDD 上下文、policy、变更意图、部分错误、foreign/raw adoption）和四项行为变异（绕过 prepare、漏 scope_end、漏 busy release、使用错误请求来源）。scope/instance/native host 是模型，完整 managed registry/host 本体由现有 host fixture 验证。

完整 host fixture 新增三组创建/挂接/部分错误退出，运行实际生产 instance、module/device pins、scope 和 typed controller；runtime/BSSID 等原生配置部分是边界模型，不据此宣称 firmware 生效。既有真实 prestart/MC/native reset 组合另行保持回归。100 项本地 Python 回归、py_compile 和 diff 检查通过；原生执行和完整目标编译集中在一轮 Actions。

0169 Actions [42837056822](https://github.com/xxz3312/XAirDrop-17/actions/runs/42837056822) 八项必需任务已全部 success，包括完整 WLAN 编译/严格链接。

跨轮询原生父级 lease、retry ordinary-tail/peer-reset 扩展、完整公开初始化/START、Apple 发现/握手/双向传输仍待完成；手机无需操作。
