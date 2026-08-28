# Actor Core 的 AccuRIG 手工交接

> 本机只保留独立 AccuRIG 与其可能依赖的 `RLHostService`/本地 CMS 共享组件。Reallusion Hub 的 Startup 链接、`RLHub_SkipUac` 计划任务、公共 `LiveUpdate` 程序和安装包目录已于 2026-08-27 删除；它不再随系统启动或弹出提示，也不是 Studio 工作流依赖。

AccuRIG 与 Actor 一对一。不要把其他 Actor 的骨骼 FBX 回传到当前条目。

## 当前待标定文件

仓库相对路径：

`workspace/actor_core/actor_core_v6_seed20260867_hy3d_v1/accurig_handoff/actor_core_v6_seed20260867_v1_accurig_input.fbx`

当前校验值：

- 大小：3,404,620 bytes
- SHA-256：`58EEE78C366671CE9714BD8206AE4824B65E5BA52DC34BDFC74F471F302AA4EF`
- 网格：61,002 vertices / 122,000 faces
- 姿态：Relaxed A；biped；无手指要求；不强制左右对称
- 用途：实验绑定与模块配件链验证；头顶轻微低频起伏是已记录问题，不代表最终生产 canonical 已批准

## 操作

1. 在 AccuRIG 打开上述 FBX。
2. 依次确认 pelvis/spine/neck/head、shoulder/elbow/wrist、hip/knee/ankle/toe，以及双侧 EarRoot 高度。
3. 完成绑定并从 AccuRIG 导出一个 FBX。不要覆盖输入文件。
4. 启动 Studio，在当前 Actor 的 3D 条目中点击“选择骨骼 FBX”。
5. Studio 将文件复制到 `workspace/actor_core/<asset-id>/manual_accurig/intakes/<intake-id>/`，执行结构验证并生成四方向预览。

## 当前新 Actor 回传结果

尚未回传。请勿选择旧 Actor 的已绑定 FBX；AccuRIG 与网格是一对一关系。

## 旧技术基线回传结果

- 原始导出：`actor_core_0ef398ca_v1_accurig_input_rigged.fbx`
- SHA-256：`76CDFB3B70A357625DC5CFEEA95F033D49A06871DCF1BE4477255DE0DF4FE065`
- Intake：`371745cc45fd472a88e75478a09ea60d`
- 状态：`ready`；101 bones；无缺失必需骨；0 未权重顶点；尺度漂移约 `0.00012%`
- 运行时副本：每顶点最多 4 influences；原始 AccuRIG 权重副本同时保留。

该旧结果只证明 intake、预览和动作适配代码可工作，不是新 Actor 的绑定文件。新 Actor 的验证失败 intake 会从 Studio 和本地工作区删除；新 FBX 静态四方向 Gate 通过后，下一道 Gate 才是选择 Mixamo 动画并检查重定向后的动态形变。详见 [骨骼动画资产与自动适配](ANIMATION_RETARGET.md)。
