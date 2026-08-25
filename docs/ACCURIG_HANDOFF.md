# Actor Core 的 AccuRIG 手工交接

AccuRIG 与 Actor 一对一。不要把其他 Actor 的骨骼 FBX 回传到当前条目。

## 当前待标定文件

仓库相对路径：

`workspace/actor_core/0ef398ca94d445f18226a8bf2a991c79/accurig_handoff/actor_core_0ef398ca_v1_accurig_input.fbx`

当前校验值：

- 大小：3,518,076 bytes
- SHA-256：`D83468F0B98A2BFA31C1293D7F92168E8D843313EB9DE6C399E92347D302BA8B`
- 网格：61,002 vertices / 122,000 faces
- 姿态：Relaxed A；biped；无手指要求；不强制左右对称

## 操作

1. 在 AccuRIG 打开上述 FBX。
2. 依次确认 pelvis/spine/neck/head、shoulder/elbow/wrist、hip/knee/ankle/toe，以及双侧 EarRoot 高度。
3. 完成绑定并从 AccuRIG 导出一个 FBX。不要覆盖输入文件。
4. 启动 Studio，在当前 Actor 的 3D 条目中点击“选择骨骼 FBX”。
5. Studio 将文件复制到 `workspace/actor_core/<asset-id>/manual_accurig/intakes/<intake-id>/`，执行结构验证并生成四方向预览。

## 当前回传结果

- 原始导出：`actor_core_0ef398ca_v1_accurig_input_rigged.fbx`
- SHA-256：`76CDFB3B70A357625DC5CFEEA95F033D49A06871DCF1BE4477255DE0DF4FE065`
- Intake：`371745cc45fd472a88e75478a09ea60d`
- 状态：`ready`；101 bones；无缺失必需骨；0 未权重顶点；尺度漂移约 `0.00012%`
- 运行时副本：每顶点最多 4 influences；原始 AccuRIG 权重副本同时保留。

验证失败的 intake 会从 Studio 和本地工作区删除。当前 intake 的静态四方向 Gate 已由用户确认为通过；下一道 Gate 是从 Studio 选择 Mixamo 动画并检查重定向后的动态形变。详见 [骨骼动画资产与自动适配](ANIMATION_RETARGET.md)。
