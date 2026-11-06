# 0134 原厂 CNSS2 常驻：上游参考与独立部署合同

状态：设计约束已整理，未实现可安装模块或设备端执行器。不得将本文当作手机操作步骤。

## 优先参考的上游

- XAirDrop：891ffe6ccf040fdc86975b4fc649add002dbebcb，module/action.sh、module/service.sh、module/customize.sh。
- OPAirDrop：28a3a1dbc9f515fa5705417a3973616e5ae6180d，module/bin/control.sh、module/service.sh、module/post-fs-data.sh。

| 项目 | 上游处理 | 小米 17 初始实现合同 |
| --- | --- | --- |
| 驱动切换 | 两者停止 Wi-Fi/HAL 后替换 WLAN，保留原厂 CNSS2 | 原厂 CNSS2 常驻；执行器不提供 cnss2 remove/insert 操作 |
| 加载前后身份 | OPAirDrop 检查运行栈身份和同 boot 所有权 | 开始、WLAN 卸载后及加载后均核对原厂 CNSS2 note；状态/holder 单独检查，不能用 cnss2 文件存在替代 |
| 框架命令日志 | XAirDrop 的 fw 和 wifi_state 使用命令替换捕获 stderr/stdout 后写日志 | 采用相同捕获原则，保留命令退出码；不能直接把共享存储日志 FD 传给系统服务，不能吞掉失败并默认 Wi-Fi 开启 |
| 启动时机 | 开机完成后调用启动流程；XAirDrop 另等待 30 秒 | 沿用开机后路线，先完成手动一次验证；不假定 KSU 可以赶在首次驱动加载前覆盖文件 |
| 重启循环防护 | XAirDrop autostart.running；OPAirDrop startup-incomplete/disabled | 在任何运行改变前持久化未完成标记；新 boot 发现未完成即禁止自动启动，保留记录 |
| 恢复 | 两者有普通失败时恢复原厂的流程 | 初版仅承诺禁用入口并重启恢复原厂。0132 已发生重启，新增分支尚无安全热回退证据，不能直接照搬自动热回退 |
| 互斥 | XAirDrop mkdir 锁；OPAirDrop flock | 独立状态/锁，与原 pairctl 互斥；旧 intent 事务必须先保留和核对，不自动删除或重放 |
| 模块管理器 | 上游提供安装、启动和设置入口 | 最终提供 KSU 可用入口；未验收的 ELF 不进入自动启动安装包 |

## 允许的初始运行序列

1. 只读门禁：设备/固件/boot、完整内核版本、原厂 CNSS2/WLAN 身份、候选文件摘要、旧事务/额外热点接口、原厂 CNSS2 导入门禁和完整 ABI 报告。
2. 备份原厂 WLAN 与实际 Wi-Fi/HAL 状态，固定清单和 boot-id；持久化未完成标记。
3. 确认 Wi-Fi 关闭、HAL 停止，原厂 WLAN 引用/holders 满足普通卸载条件；卸载原厂 WLAN。
4. 重新确认同一原厂 CNSS2 仍 live 且其 holders 符合阶段预期，加载 provider 与新 WLAN。默认无线实验参数保持关闭，不在这一阶段混入 mac80211/Wonder/AWDL 激活。
5. 核对新 WLAN/provider note、原厂 CNSS2 note 和依赖关系，恢复原始 HAL/Wi-Fi 状态。只有全部检查完成才记录 active。

每个副作用需记录执行前 intent 和返回码，再记录完成；任何中断/失败停止，保留日志与事务，不自动重试、强制卸载或执行后续加载。保留原厂 CNSS2 减少了已知差异，并不能证明重启根因已修复。

## 当前构建证据

0133 源 52a9c342b9e31209fc9e4280ed0220b39672ecd4 的首次诊断作业通过 100 项 Python 测试，随后旧 wonder_provider_fixture.py 因缺少新增 mishare_wlan_execution.h 阻断，未进入 WLAN 编译。

93d2ea7571c723159dff83253003e427fd5677b9 同步生产头文件、夹具的参数声明与模型化请求返回，并测试无自动请求、拒绝非法/0 输入、显式 1 传播模型错误。实际 execution controller 由独立夹具覆盖，不把本夹具的模拟结果当作真实控制器结果。[运行 42271965465](https://github.com/xxz3312/XAirDrop-17/actions/runs/42271965465) 的 Host regression checks 已通过，完整构建仍在执行。尚无新 WLAN ELF 正向验收，不生成手机试验包。
