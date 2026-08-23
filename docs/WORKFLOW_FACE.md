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

## Actor V2 头部实测标定与完整复放

Actor V2 不再继承 Actor V1 的对称世界坐标。当前头模的加权头部中心为 `X=+0.0343 m`，因此把眼睛或耳朵硬写成 `+/-X` 会产生可见错位。每个新 Actor 必须先从 `CC_Base_Head` 权重区域和求值后头表面生成 `head_feature_calibration_v1.json`，再由眼睛、耳朵和发型三个阶段共同读取它。

当前一键入口：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\build_actor_v2_head_features.ps1 `
  -ActorBlend .\workspace\actor_v2\assembly\v2\actor_v2_base_v1_game4_eye_v2_02_miku_ears_fit_09.blend `
  -OutputDir workspace\actor_v2\head_feature_build
```

当自动贴合已经接近目标、但眼睛/耳朵仍需人工美术落位时，先在 Studio 的“五官与耳朵 → 进入手动校准”中停在 frame 1：

- 三轴手柄用于粗调；`1 mm / 1%` 按钮用于最终微调。
- 眼睛默认启用镜像联动：上下、前后和缩放同向，左右位移对称反向，避免再次形成左右漂移。
- Studio 不修改 Blend，只导出 `assetsstudio_head_feature_feedback_v1` JSON。坐标合同为 Three.js `X=右 / Y=上 / Z=向外`，不得把 GLB 的烘焙对象原点当作可见几何中心。
- Blender 的 `apply_studio_head_feature_feedback.py` 以可见几何包围盒中心为枢轴，将增量转换到 Blender `X=右 / Z=上 / -Y=向外`，并保留原 `CC_Base_Head` 父级。

校准前必须把本次候选导出为 Studio 专用预览，确保网页操作的是与 Blender 同源的 Actor V2，而不是历史 Actor V1 合成预览：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\export_studio_actor_v2_head_calibration_preview.ps1 `
  -InputBlend .\workspace\actor_v2\head_feature_hairline_fix\actor_head_complete_calibrated.blend
```

导出物固定写入 `studio/public/generated/actor-v2-head-calibration.glb` 及其 manifest；Studio 的 Face 工作台优先加载该文件。每次更换 Actor、眼睛、耳朵或发型候选后都必须重导，禁止对旧预览产生的 JSON 进行复用。

将导出的 JSON 交回完整复放入口：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\build_actor_v2_head_features.ps1 `
  -ActorBlend .\workspace\actor_v2\assembly\v2\actor_v2_base_v1_game4_eye_v2_02_miku_ears_fit_09.blend `
  -StudioFeedback .\actor-v2-head-feature-feedback-v1.json `
  -OutputDir workspace\actor_v2\head_feature_build_manual
```

手动反馈只是候选覆盖层，不能跳过眼面距离、耳根接触、头皮覆盖、四向眨眼和动作附件门禁。Studio “看起来贴合”不等于模型已经晋级。

固定顺序如下：

1. `calibrate_actor_v2_head_features.py` 从当前姿态的求值后头表面解析眼眶和左右耳根，输出世界坐标、头部归一化配方与验证阈值。
2. `build_actor_eye_assembly.py --calibration ...` 构建左右贴合曲面。Actor L 使用 viewer-named `eye_right`，Actor R 使用 `eye_left`；重跑前必须删除旧眼对象和孤立的 `EyeAssemblyV1_*` 材质，保证三态材质名幂等。
3. `fit_miku_ears_from_head_calibration.py` 从保留的 Miku 耳朵来源重建两个独立 `EarPair` 对象，逐侧投影耳根，保持 `4 mm` 接触余量。
4. 原配 Stage10/混元发束读取同一标定 JSON；可见发束保持源锁定，只允许增加由当前求值后头表面复制的隐藏发帽接口层。当前适配值为 width `1.10`、Q-height `1.15`、top `0.06 m`、radial `0.09 m`、cap bottom `0.44 m`、cap shell `0.055 m`。发帽前缘必须采用 `curved_source_bangs_occlusion_v1` 曲线发际线，高中心、低太阳穴并藏在源刘海后；平直 Z 截面会形成“发带”错觉，已禁止。
5. 不得在最终发型上删除椭球形耳洞。当前 Miku 耳朵保持耳根不动，以 outward scale `2.0` 穿出侧发轮廓；未来发型可改为声明自己的 ear-occlusion policy。
6. 必须通过眼面距离、耳根距离、四向头皮覆盖、静态眼睛合同、四向八帧眨眼和动作附件稳定性后，才可进入服装/运行时装配。

fit29 的平直前额发帽边界已因“像发带”被视觉复核否决。当前修复候选为 `workspace/actor_v2/head_feature_hairline_fix/actor_head_complete_calibrated.blend`：发帽从求值后头表面重建并使用曲线发际线，眼面中位距离仍约 `1.76 mm`，耳根中位距离约 `4.00 mm`，四向最小头皮覆盖率仍为 `0.981132`，四向八帧眨眼和 Walk `1-71` 八采样帧通过。它仍需最终视觉确认，技术通过不自动等于美术晋级。

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
