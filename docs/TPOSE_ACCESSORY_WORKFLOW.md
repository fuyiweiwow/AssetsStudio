# 未绑定 T-Pose 配件工作流

## 用途与边界

人工 AccuRIG 暂时无法完成时，配件链不必停工。Studio 允许在未绑定 T-Pose 素体上提前完成独立配件的图像生成、3D 形体、静态装配、四方向审查和本地候选生命周期。

这条支线不会跳过绑定：静态通过只代表配件在 Rest Pose 中可用。骨骼映射、蒙皮、关节形变、动作循环以及手和腿的动态间隙仍必须在人工 Rig 导入后补做。

## 与已有工作流的关系

沿用现有生产链的权威和 Gate：

`StyleProfile → 独立 Slot 权威图/本地生成候选 → Hunyuan3D-2MV → 配件拓扑 Gate → T-Pose Slot 装配 → 静态相交 Gate → 四方向人工复核 → 本地候选入库/销毁`

区别只有两点：

1. `ActorSlotProfile v2` 使用以素体高度为单位的 `position_h` 与 `bounds_h`，不依赖当前机器的绝对坐标，也不要求骨骼已经存在。
2. `future_parent_bone` 只是未来 Rig Intake 的语义映射提示，静态阶段不能声称已经绑定或通过动画。

素体继续使用单连通、watertight、法线一致、Euler=2 Gate。配件允许由腰带、扣环、扣针和腰包等多个封闭组件构成，但限制组件数量，并清除占总面数低于阈值的微小碎片。两类 Gate 不得混用。

## 当前实验代理

- StyleProfile：`qstyle_anime_western_fantasy_chibi3_no_face_v1`，目标比例 `2.9–3.1H`。
- T-Pose Profile：`actor_core_chibi3_v9b_tpose_slots_v1`。
- 代理模型：`candidates/v9b_balanced/chibi3_v9b_balanced.glb`。
- 状态：`experimental_proxy`，只作为配件适配基准，不是 production canonical，也没有 AccuRIG 批准。
- 槽位：11 个；当前具备独立生成权威的是 `waist_accessory`。

三头身 Profile 与原 `2.1–2.5H` Profile 分开保存，禁止通过扩大旧比例范围来掩盖形体差异。

## 首个闭环结果

候选：`waist_belt_pouch_chibi3_v9b_seed20260831`

- 输入为仓库已有 `waist_accessory_turnaround_v1.png`，不是规则建模成品，也没有调用在线生图。
- 本地 Hunyuan3D-2MV：20 steps、CPU offload，峰值显存 `2,898,266,112` bytes；该数字来自 RTX 5070 Ti 实验，不能替代真实 RTX 3060 12GB 资格验证。
- 原始输出 11 个封闭组件；清除一个 16 面微小碎片后保留 10 个有效组件。
- 最终网格 128,258 顶点、256,496 面，全部组件 watertight，法线绕序一致。
- XYZ 装配缩放最大轴比 `1.0306`，没有靠强烈非等比挤压修复形状。
- 素体与配件表面三角形相交数为 0，四方向预览完整。
- 当前状态为 `pass_static_tpose_manual_review_required`，只进入本地候选，不自动入库。

## 一键实验入口

```powershell
.\tools\run_tpose_accessory_experiment.ps1 -Seed 20260832
```

脚本会搜索 Python、Blender、Hunyuan3D 源码与模型环境；公共模型仍由现有环境发现和 ModelScope 安装流程负责，文档不绑定机器绝对路径。

仅检查环境搜索结果：

```powershell
.\tools\run_tpose_accessory_experiment.ps1 -CheckEnvironment
```

常用选项：

```powershell
# 已存在同 seed 的 Hunyuan shape 时复用，只重新装配和预览
.\tools\run_tpose_accessory_experiment.ps1 -Seed 20260832 -ReuseShape

# 只生成并验证，不注册到 Studio 候选列表
.\tools\run_tpose_accessory_experiment.ps1 -Seed 20260832 -NoRegister
```

输出只写入忽略 Git 的 `workspace/accessory_fit/` 与 `workspace/local_3d_generation/accessories/`。人工在 Studio 勾选全部静态 Gate 后才能加入本地 3D 配件库；失败候选应直接销毁。

## Rig 完成后的升级

人工 AccuRIG 导入后，按照 `future_parent_bone` 将 Rest Anchor 映射到实际骨骼，并新增以下 Gate：

1. 腰部、脊柱和髋部权重映射；
2. 关节弯曲后的表面穿插；
3. `mixamo_standard_walk_v1` 四方向循环；
4. 手臂摆动与腰包间隙；
5. 大腿抬起与腰带、腰包间隙；
6. 动态通过后把候选状态升级为可用于 Recipe 的正式配件资产。
