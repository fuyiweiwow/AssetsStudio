# 五官当前工作流：头部贴合 EyeAssembly、眨眼与3渲2

## 当前合同

本节描述的是 **Actor V1 兼容基线**。其中耳朵内嵌于 Face Actor，是已经存在的运行时实现，不是 Actor V2 的目标结构。Actor V2 不得把这个历史实现误当成新基体合同。

五官不再拥有独立的 `milestones/face/` 运行时或渲染里程碑。当前唯一正式合同是：

- Face 合同：`milestones/body/face_contract_v2.json`
- 身体/Walk 保留基线：`milestones/body/chibi_actor_mixamo_walk_v1.blend`
- 当前 Face Actor：`milestones/body/chibi_actor_eye_assembly_v2.blend`
- 头骨：`Armature/CC_Base_Head`
- 眼睛对象：`EyeAssemblyV1_Front_L/R`
- 眼睛状态：`open / half / closed`
- 确定性眨眼：`open → half → closed → half → open`，随后保持睁眼直到下一轮 Walk
- 眼睛源纹理：`milestones/body/eye_textures/eye_*.png`
- 3D耳朵对象：`MikuEar_L_SourceV1`、`MikuEar_R_SourceV1`
- 耳朵原始来源：`references/face/miku_chibi_source/miku_chibi_source.fbx`

眼睛和耳朵均已父级到 `CC_Base_Head`。眼睛使用同一套贴合头部浅曲面切换三种状态材质，不再使用旧 `EyePackageV1` 的框架/镜片叠层。原始 Miku FBX 是包含完整角色的私有来源文件，只用于可复现地提取耳朵，不能作为运行时耳朵直接载入。

## Actor V2 耳朵槽迁移

Actor V2 将耳朵从 Face Actor 拆分为可变化标准件：

- 基体头部不得焊接、雕刻或导出永久耳朵，只保留左右耳根标准定位点与贴合边界。
- 槽名为 `EarPair`；一个槽资源包含左右两个独立网格对象，但以同一 bundle/variant 管理，避免左右风格不一致。
- 默认人类耳、精灵耳和后续幻想种族耳均走同一槽合同；不得为每种耳型复制 Actor 头部。
- 耳朵对象绑定 `CC_Base_Head`，并记录左右定位、缩放、接缝遮盖范围和与发型/头饰的净空要求。
- Actor 多视图和 Hunyuan 基体输入使用无永久耳朵版本；耳朵候选另行生成或建模，再进入 `EarPair` 标准件流程。
- 四向静态与动作验收必须检查耳根缝隙、穿头、左右错配、发型遮挡和随头漂移。

`milestones/body/face_contract_v2.json` 继续只代表 Actor V1 技术基线；在 Actor V2 获得静态多视图验收前，不覆盖该文件。

Blender 权威 Face 保持 Bone Parent 合同；导出 Studio GLB 时，脚本先在 REST pose 烘焙同一贴合曲面，再把所有眼睛顶点 100% 赋权给 `CC_Base_Head`。网页端必须得到带 `skin` 的 SkinnedMesh，不能把普通 Bone Child 节点当作已完成网页绑定。`tools/validate_studio_actor_preview.py` 会拒绝任何没有 `skin` 的眨眼状态节点。

## 重建与眨眼审查

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\build_actor_eye_assembly.ps1
powershell -ExecutionPolicy Bypass -File .\tools\render_actor_eye_blink_review.ps1
```

第一条命令从保留的 Actor/Walk 基线生成 Face v2，并验证眼睛是否 Bone Parent 到 `CC_Base_Head`、是否包含三态材质、frame 1 到 31 是否随头部移动。第二条命令输出四方向 × 8 帧眨眼审查材料到 `workspace/face/eye_assembly_v2/`；它不改变身体采样。

## Actor 3渲2闭环

四方向3D渲染：

```powershell
& E:\Env\Blender\blender.exe --factory-startup --background `
  --python .\tools\blender\render_accurig_chibi_walk_test.py -- `
  --input-blend .\milestones\body\chibi_actor_eye_assembly_v2.blend `
  --output .\workspace\actor_3to2\render `
  --frame-count 8 --soft-toon-lighting
```

像素化和 GIF/Sprite Sheet：

```powershell
python .\tools\process_actor_3to2_pixels.py `
  --render-dir .\workspace\actor_3to2\render `
  --output-dir .\workspace\actor_3to2\pixels `
  --size 64 --frame-count 8 --fps 8 --replace

python .\tools\validate_actor_3to2_pixels.py `
  --asset-dir .\workspace\actor_3to2\pixels
```

所有输出默认位于 `workspace/`，不进入 Git。只有未来明确晋级的美术基准或 BomboAdventure 发布包才允许同步。

## 保留的能力

- 当前 Actor 的 EyeAssembly、眉眼外观和3D耳朵随骨骼动作渲染。
- open/half/closed 三态和确定性眨眼可在 Blender 审查输出与 Studio 交互预览中复现。
- `render_accurig_chibi_walk_test.py` 可选择受限 Face style bundle，用于后续随机化研究。
- `replace_with_miku_source_ears.py` 保留耳朵来源重建能力。
- `render_actor_clothing_eevee.py` 让衣物和鞋使用同一 Actor、Face 和动作合同生成审查帧。

## 已退休内容

- `milestones/face/base_features_v1/`：旧2D男女 Face/耳朵帧。
- `milestones/face/runtime_chibi_eyes_ears_walk_v1/`：旧2D运行时证明包。
- Face 随机化 contact sheet 与旧 Gallery。

它们留在 AssetsLab 历史中，不是当前 Actor 的正式输入。

## 晋级门槛

- 正、右、背、左四向一致；背面不出现正面五官投影。
- 眼睛和耳朵随 `CC_Base_Head` 运动，不漂浮。
- 新五官变体必须直接在当前 Actor 上预览并记录 Recipe/seed。
- 最终结果符合 `docs/ART_DIRECTION.md`，并通过页面预览和3渲2 GIF 人工审查。
