# 五官当前工作流：Actor 内嵌3D组件与3渲2

## 当前合同

五官不再拥有独立的 `milestones/face/` 运行时或渲染里程碑。当前唯一正式合同是：

- Face 合同：`milestones/body/face_contract_v1.json`
- Actor：`milestones/body/chibi_actor_mixamo_walk_v1.blend`
- 头骨：`Armature/CC_Base_Head`
- 眼睛对象：`EyePackageV1_AlmondFrame_L/R`、`EyePackageV1_Lens_L/R`
- 眼睛源纹理：`milestones/body/eye_textures/eye_left.png`、`eye_right.png`
- 3D耳朵对象：`MikuEar_L_SourceV1`、`MikuEar_R_SourceV1`
- 耳朵原始来源：`references/face/miku_chibi_source/miku_chibi_source.fbx`

眼睛和耳朵均已父级到 `CC_Base_Head`。原始 Miku FBX 是包含完整角色的私有来源文件，只用于可复现地提取耳朵，不能作为运行时耳朵直接载入。

## Actor 3渲2闭环

四方向3D渲染：

```powershell
& E:\Env\Blender\blender.exe --factory-startup --background `
  --python .\tools\blender\render_accurig_chibi_walk_test.py -- `
  --input-blend .\milestones\body\chibi_actor_mixamo_walk_v1.blend `
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

- 当前 Actor 的眼睛、眉眼外观和3D耳朵随骨骼动作渲染。
- `render_accurig_chibi_walk_test.py` 可选择受限 Face style bundle，用于后续随机化研究。
- `replace_with_miku_source_ears.py` 保留耳朵来源重建能力。
- `render_actor_clothing_eevee.py` 让衣物和鞋使用同一 Actor、Face 和动作合同生成审查帧。

## 已退休内容

- `milestones/face/base_features_v1/`：旧2D男女 Face/耳朵帧。
- `milestones/face/eye_assembly_v1/`：旧 ImageGen half/closed 眼睛装配测试。
- `milestones/face/runtime_chibi_eyes_ears_walk_v1/`：旧2D运行时证明包。
- Face 随机化 contact sheet、Gallery 和 eye assembly 测试脚本。

它们留在 AssetsLab 历史中，不是当前 Actor 的正式输入。

## 晋级门槛

- 正、右、背、左四向一致；背面不出现正面五官投影。
- 眼睛和耳朵随 `CC_Base_Head` 运动，不漂浮。
- 新五官变体必须直接在当前 Actor 上预览并记录 Recipe/seed。
- 最终结果符合 `docs/ART_DIRECTION.md`，并通过页面预览和3渲2 GIF 人工审查。
