# 身体与骨骼动画工作流

## 基线

- 场景：`milestones/body/chibi_actor_mixamo_walk_v1.blend`
- 原演员：`milestones/body/actor_accurig_input.fbx`
- Walk：`milestones/body/animation_sources/mixamo_standard_walk.fbx`
- Run：`milestones/body/animation_sources/mixamo_run.fbx`
- 网格：`ChibiBaseMesh_AccuRIG_InputMesh`
- 骨架：`Armature`
- Walk 审查帧：`1, 11, 21, 31, 41, 51, 61, 71`

## 重定向

使用 `tools/blender/retarget_mixamo_to_accurig_actor.py`。不要重新做 Mixamo 自动绑骨；动作应映射回同一套 `CC_Base_*` 骨架，否则五官、耳朵、衣物和鞋的权重合同会失效。

```powershell
& E:\Env\Blender\blender.exe --background --python .\tools\blender\retarget_mixamo_to_accurig_actor.py -- `
  --actor .\milestones\body\chibi_actor_mixamo_walk_v1.blend `
  --mixamo-fbx .\milestones\body\animation_sources\mixamo_standard_walk.fbx `
  --output .\workspace\body\actor_walk_candidate.blend
```

## 验收

- 四方向使用同一相机合同和同一脚底基线。
- 明显看到大腿、膝、手臂和躯干逐帧变化。
- 眼睛、耳朵、眉毛和未来头饰继续跟随 `CC_Base_Head`。
- 衣物与鞋的 GIF 必须使用同一组 8 个动作帧。

