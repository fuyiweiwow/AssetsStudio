# 发型里程碑与随机化工作流

## 权威输入

- 女性源：`milestones/hair/Blender-Chloe_Hair.blend`
- 男性源：`milestones/hair/male_source/Blend_Hair.blend`
- 组件目录：`milestones/hair/hair_component_catalog_v1.json`
- 正式随机池：`milestones/hair/hair_random_pool_v1.json`
- Gallery 注册表：`milestones/hair/hair_gallery_catalog_v1.json`

发型不是任意网格笛卡尔积。装配顺序固定为：Actor 头部锚点 → 必选 `base_cap` → 后发 → 侧发 → 刘海 → 后部附件 → 四视图审查。运行时按 seed 选择已经验收并固化的完整 bundle，不在游戏内运行 Blender。

## 两种随机化

1. 组件组合随机：从正式池按槽位和兼容关系组装候选。
2. 单组件几何变体：只改变一个参考组件的宽度、深度、高度、轮廓或旋转，先审查再入池。

工作台工具：

- `tools/build_hair_workbench.py`
- `tools/build_hair_component_workbench.py`
- `tools/build_hair_randomization_gallery.py`
- `tools/build_hair_gallery_index.py`
- `tools/blender/generate_hair_component_variant.py`
- `tools/blender/generate_hair_component_preview.py`
- `tools/blender/generate_hair_component_assembly.py`

## 晋级门槛

- base 必须存在；附件不能替代 base。
- 正、右、背、左都不能露头皮、穿耳或缺后脑覆盖。
- 候选记录 seed、组件 ID、源 Blend 和生成参数。
- 只有人工认可的组件才能写入正式随机池；只有人工认可的组合才能固化为运行时 bundle。

