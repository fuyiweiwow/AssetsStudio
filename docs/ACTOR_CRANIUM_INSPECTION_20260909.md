# 脑壳静态检查（2026-09-09）

结论：当前修脚版未绑定模型的八向头部特写未见明显的大面积脑壳内陷；可见浅小坑、轻微表面起伏及脸部残留折痕。静态检查不能复现或排除用户在 AccuRIG 动画预览中看到的凹陷，目前没有依据为此重新生成全身或改动头部。尚未获得该模型的已绑定回传文件。

## 检查对象和证据

- 当前模型：`workspace/local_generation/actor_foot_repair_20260908/local_v2/foot_candidate.glb`。
- 修脚前对照：`workspace/local_generation/actor_offline_gate_20260908/static_50k_v2/actor_offline_v2_50k_rig_mesh.glb`。
- 交换文件：`workspace/local_generation/actor_foot_repair_20260908/local_v2/accurig_input/Actor_Offline_v2_FootRepair_AccuRIG.fbx`。
- 结果目录：`workspace/local_generation/actor_cranium_inspection_20260909/`。`report.json` 保存输入 SHA256、头部双向最近顶点距离和真实表面截面采样。
- 使用 Blender 4.5.10 后台渲染正、右、背、左、顶及三个斜上视角；无纹理、无地面、无阴影和 cavity 增强，保留平滑法线及工作室高光以观察表面。

头部比较区域为世界坐标高度大于 `min_z + 0.60H`，包括脸与耳。修脚前后该区域均有 9,313 个顶点，双向最近顶点最大距离为 **0**。FBX 导入后该区域仍为 9,313 个顶点，最大误差为 **3.2782554626464844e-07**，相对全高约 **1.65e-7**。这表明脚底修复和此 FBX 导出没有引入脑壳变形。

从上方向下射线采样头顶中央左右、前后两条截面，每条 201 点，间隔 `0.0024H`。在跨度 `0.048H` 的对称邻点弦线检查中，两条截面均未出现中点低于弦线的情况。左右截面存在一个非常浅的采样局部极小值，因此不将结果描述为绝对光滑或全表面无凹陷。两条截面也不能替代整个头壳的检查。

所有输入文件哈希保持不变。本次只新增只读检查脚本、诊断图和报告，没有修复、重新生成、绑定或批准模型。

## 后续判断

当前证据支持保留现有模型，等待同一 Actor 的 AccuRIG 工程或含网格与骨架的导出 FBX，再检查头部骨骼落点、顶点权重及导致凹陷的具体姿态。浅小坑属于独立静态美术问题；去掉它们不能宣称解决动画凹陷。此次没有做动态、全身自交或蒙皮质量认证。

## 复现

使用已发现的 Blender 可执行文件运行（输出目录必须不存在）：

```powershell
& $Blender -b -t 4 --python tools/model_test/inspect_actor_cranium_blender.py -- `
  --input workspace/local_generation/actor_foot_repair_20260908/local_v2/foot_candidate.glb `
  --baseline workspace/local_generation/actor_offline_gate_20260908/static_50k_v2/actor_offline_v2_50k_rig_mesh.glb `
  --fbx workspace/local_generation/actor_foot_repair_20260908/local_v2/accurig_input/Actor_Offline_v2_FootRepair_AccuRIG.fbx `
  --output workspace/local_generation/actor_cranium_inspection_repeat
```
