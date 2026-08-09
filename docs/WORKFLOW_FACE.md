# 五官工作流：眼睛、眉毛与耳朵

## 当前合同

- open 眼睛权威资源：`milestones/body/eye_textures/eye_left.png` 与 `eye_right.png`。
- open 眉眼比例与风格随上述贴图固定；随机样式生成器只做有边界的眼睛比例、高度和眉形调整。
- 耳朵源：`milestones/body/ear_source/miku_chibi_ear_source.fbx`，最终对象绑定 `Armature/CC_Base_Head`。
- half/closed 眨眼状态：`milestones/face/eye_assembly_v1/`。
- 已通过技术闭环的旧 2D 包：`milestones/face/runtime_chibi_eyes_ears_walk_v1/`；它是运行验证，不替代 Actor V1 美术基线。

## 随机化

`appearance_seed` 必须稳定映射到受限的眼睛/眉毛样式；同一 seed 永远得到同一结果。耳朵保持已验证挂接，除非另开耳朵变体审核。

相关工具：

- `tools/blender/render_accurig_chibi_walk_test.py`
- `tools/run_chibi_face_randomization_preview.ps1`
- `tools/build_chibi_face_variant_contact_sheet.py`
- `tools/build_chibi_face_randomization_gallery.py`
- `tools/validate_chibi_face_randomization.py`
- `tools/blender/build_eye_assembly_v1.py`
- `tools/blender/render_eye_assembly_blink_walk.py`

## 眨眼

只在同一套头部父级表面切换 `open → half → closed → half → open`；禁止重新引入独立侧面 PNG 平面。背面必须没有眼睛，侧面必须来自同一 3D 表面的自然投影。

## 晋级门槛

- 正、侧、背、左四向一致；背面眼睛透明。
- 眼睛、眉毛、耳朵随头骨运动，不漂浮。
- 随机样式必须有 seed、样式 ID 和预览 manifest。
- 最终随机五官要先导出为独立 Face 层，不能直接改写身体动作帧。

