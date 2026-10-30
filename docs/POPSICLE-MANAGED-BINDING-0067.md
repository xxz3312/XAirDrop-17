# 0067：provider与Wonder的实际managed绑定

0066只有内部生命周期接口，没有安装绑定调用方。0067把默认关闭的mishare_wonder_attach绑定接到真实的WLAN provider、component master与Wonder入口。

## 本轮实现

- 私有provider通过独立side channel传递managed descriptor，原wondertap_ops/priv布局和旧setter不变。QUERY/CLAIM/RELEASE由独立mutex保护，不在该mutex下调用component_add/del，支持同步bind/unbind回调。
- Wonder在发布ops前先关闭启动准入，由模块加载器保持私有provider依赖、绑定回调owner模块，再登记cookie和quiesce回调；CLAIM成功后才开放准入。竞争到closing时回滚，不临时开放init。
- provider清除前先quiesce消费者。有句柄、异步回收或隔离状态时返回错误，保留component、descriptor和claim；拒绝新QUERY/CLAIM/重复注册。消费者显式完成retire后可重试清除。
- RELEASE与quiesce共用claim mutex，RELEASE返回前cookie必须保持存活。quiesce仅关闭准入/检查本地归属，不能递归调用provider/component或提交无线清理。
- component master实际调用managed绑定/解绑。小米17构建直接导入私有provider接口，模块加载器维持依赖；通用构建和旧setter走同步路径。解绑后准入保持关闭，下一次绑定重新分阶段开放。
- managed绑定收到NETDEV_DOWN/UNREGISTER时关闭准入并停止队列，保留句柄/引用；SSR worker拒绝自动features_exit/init；旧同步恢复与新绑定共用恢复准入门，恢复期间拒绝bind/init，避免检查后绑定穿入。wondertap_prep移至对象创建、register_hw之前，仅构造一次。这只是本地fence，不是native恢复或父资源租约。
- 最终free发现仍有managed binding、provider claim或实例引用时保留Wonder内存。HDD unregister返回错误并保留owner/closing状态，不把失败当作解除成功。

## 未完成且不能混淆的部分

**当前HDD init仍返回EOPNOTSUPP，不创建无线会话。** managed descriptor的poll/retire回调也不会分配资源或发送固件命令；这里只让原有可选元数据绑定真正经过新传递路径。它不是17专用会话与Wonder的功能联通。

已核对目标__hdd_soc_remove/hdd_soc_remove是void回调；底层remove/SSR不能仅靠上层EBUSY保证不拆父资源。现有native remove调用方尚未处理新的unregister返回值。只有本轮HDD后端保证无无线资源时才可维持该路径；接入创建/启动前，必须补齐native父资源租约、已准备/已启动会话的SSR恢复及完整停机协调。不能在当前init里直接调用0065的host session_step。

独立的完整monitor packet DMA、辅助monitor、地址过滤和native RAW仍未接通。没有AirDrop成功或新增手机收包证据，本轮不发手机测试包。

## 验证方法

新增C integration fixture直接编译生产provider、HDD metadata、Wonder core和provider binding helper，提取生产component master bind/unbind和mac80211最终free函数执行；平台/component服务、模块引用、mutex及版本接受使用模型。测试真实绑定、模块拒绝、错误回滚、重复/错误owner、忙时保留、关闭后禁止启动、显式回收后解绑、重绑定、legacy兼容及仍有归属时拒绝free。

测试中的可启动假后端仅用于制造busy/retire条件，不代表目标固件会话。模型不证明真实锁并发、component框架、物理remove、SSR父资源或空口。完整内核构建与严格链接单独记录。

严格modpost确认目标GKI不提供__symbol_get/__symbol_put，因此没有使用动态查询或绕过符号检查。POPSICLE_STOCK_MAC80211_ABI构建显式启用私有provider导入，Wonder modpost使用本轮真实provider Module.symvers；其他构建不导入该私有符号。
