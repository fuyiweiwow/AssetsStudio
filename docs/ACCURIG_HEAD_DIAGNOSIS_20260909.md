# 1.fbx 脑壳变形诊断

后续已完成独立头部权重修复候选，文件与验证边界见 [修复交接](ACCURIG_HEAD_REPAIR_20260909.md)。以下保留修复前诊断。

已在后台 Blender 4.5.10 中复现明显的脑壳凹陷与折叠，直接原因是上部脑壳存在胸椎骨骼权重：部分脑壳跟随 `CC_Base_Spine02`，其余跟随 `CC_Base_Head`，头颈相对胸部旋转时发生强烈拉扯。此结果支持先修复蒙皮，无需为当前缺陷重新生成全身。尚未诊断自动权重为何产生这种分配，也不把骨骼落点是否最优视为已验收。

## 输入与范围

- 用户文件：`workspace/local_generation/actor_foot_repair_20260908/local_v2/accurig_input/1.fbx`。
- SHA256：`58435dada868a5e7f0c67ae178dd5f7118979b70a033171d149962ae8eeee825`。
- 一个网格、一个骨架，26,115 顶点、52,226 面、71 骨骼。
- 文件只含单帧 T-Pose，没有昨晚预览的动作片段。本次使用头、两节颈骨、两节胸椎的局部三轴 ±30° 共 30 个单骨骼旋转探针；不是原 AccuRIG 动作回放。
- 中性 Pose 与 Rest 顶点最大位移为 0。相对未绑定交接 FBX，全身双向最近顶点最大距离为 0.0127295（约 0.64% 全高）；顶点/面数相同不代表几何完全相同，本次不把该差异归因于特定导出步骤。

## 上部脑壳权重

诊断区域：世界坐标 `z > min_z + 0.80H`，仅上部脑壳，共 4,987 顶点、14,734 条内部边。

- `Head` 平均权重 80.564%，`Spine02` 平均权重 **19.436%**。
- **936** 个顶点的最大权重来自 `Spine02`。
- **1,510** 个顶点的 `Head` 权重低于 0.95。
- 权重总和范围 0.9999902–1.00000003，因此仅检查归一化或有无未加权顶点无法发现此问题。

最严重压缩探针为 `CC_Base_NeckTwist01` 局部 Y 轴 +30°：脑壳最短边长比 **0.031888**（相对静态缩短约 96.8%），最大比值 **4.497985**；972 条边压缩超过 10%，1,859 条边拉长超过 10%。正、侧、顶视可见大块凹陷和折叠。

## 因果对照（不是修复交付）

仅在进程内临时把 `z > min_z + 0.60H` 的 9,313 个顶点设为 `Head=1`，保持网格、骨架和同一最差姿态不变。上部脑壳边长比回到 **0.999951–1.000045**，超过 10% 的压缩/拉伸边均为 **0**，脑壳大面积凹陷消失。

这个高度截断是隔离权重因素的实验，不是生产蒙皮方法。侧视仍能看到截断边界附近的脸部/下头部折痕，不能把它交付为已修复模型。最终修复需要按实际头部、下颌、耳根与颈部连接建立连续权重，保护身体权重，并重新验证多姿态与四方向。

原始输入文件哈希检查不变；没有保存修改后的 FBX/GLB/Blend，没有导入 Studio 或资产库。实验结束前恢复了临时权重。

## 证据与复现

最终报告与 15 张图：`workspace/local_generation/accurig_head_inspection_20260909_control/`。

- `rest_*.png`：静态基线。
- `worst_probe_*.png`：原始权重下的最差探针。
- `weight_control_*.png`：相同姿态的进程内权重对照，不能用于资产交付。
- `report.json`：完整骨骼落点、异常顶点权重、30 个探针和对照指标。

```powershell
& $Blender -b -t 4 --python tools/model_test/inspect_accurig_head_blender.py -- `
  --input workspace/local_generation/actor_foot_repair_20260908/local_v2/accurig_input/1.fbx `
  --reference workspace/local_generation/actor_foot_repair_20260908/local_v2/accurig_input/Actor_Offline_v2_FootRepair_AccuRIG.fbx `
  --output workspace/local_generation/accurig_head_inspection_repeat
```

`$Blender` 为已发现的可执行文件，输出目录必须不存在。
