# 短袖上衣当前工作流

## 选择

当前只保留 Actor-native 单网格路线：从 Actor 躯干与上臂表面选面，保留原骨骼权重，沿法线给少量净空，整理衣摆和袖口边界。它不导入 Colin 衣服，也不把 GarmentCode demo 尺寸当 Actor 尺寸。

当前候选：`milestones/tops/actor_native_tshirt_v5/`。

## 已知缺陷

右肩/右袖在非对称走路姿态中仍会露出突出块。此前缩短袖长、去掉 Solidify 壳、改变全局净空都没有消除它，因此不得再次重复这些对照实验。候选状态固定为 `provisional`，直到局部肩袖边界拓扑被真正修复并通过人工 GIF 审查。

## 生成新候选

```powershell
& E:\Env\Blender\blender.exe --background --python .\tools\blender\build_actor_native_tshirt_body_component.py -- `
  --actor-blend .\milestones\body\chibi_actor_mixamo_walk_v1.blend `
  --output .\workspace\tops\actor_native_tshirt_candidate `
  --bottom-z 0.70 --top-z 1.48 --torso-half-width 0.50 `
  --sleeve-fraction 0.80 --clearance 0.012 --shell-thickness 0.008 --resolution 256
```

## 审查顺序

1. 正面：衣身覆盖、肩袖连续、手与下摆无黏连。
2. 右侧：袖管绕上臂延伸、袖口开口可读、肩部不穿模。
3. 背面：肩部连续，衣片不错位。
4. 四向动画：骨骼动作明显，衣摆和袖口没有帧间碎片。

自动报告只能保持或降低状态，不能替代人工晋级。

