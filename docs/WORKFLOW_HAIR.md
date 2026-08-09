# 发型里程碑与随机化工作流

## 权威输入

- 女性源：`milestones/hair/sources/female/chloe_hair_source.blend`
- 男性源：`milestones/hair/sources/male/colin_hair_source.blend`
- 组件目录：`milestones/hair/hair_component_catalog_v1.json`
- 正式随机池：`milestones/hair/hair_random_pool_v1.json`
- Gallery 注册表：`milestones/hair/hair_gallery_catalog_v1.json`
- 首套网页候选配方：`milestones/hair/first_bundle_recipe_v1.json`

发型不是任意网格笛卡尔积。装配顺序固定为：Actor 头部锚点 → 必选 `base_cap` → 后发 → 侧发 → 刘海 → 后部附件 → 四视图审查。运行时按 seed 选择已经验收并固化的完整 bundle，不在游戏内运行 Blender。

## 首套 Actor Bundle

当前只接入一套固定女性候选 `female_chloe_seed_04_bangs04`，组件为 `Chloe_hair_back_01 + Chloe_hair_side_01 + Chloe_hair_bangs_04`，沿用既有 `q_height_ratio=1.15`、`width_ratio=1.18`。它在网页 GLB 中转换为 100% `CC_Base_Head` 单骨蒙皮，以保证跟随 Walk 而不独立漂浮。

```powershell
cd .\studio
npm.cmd run assets:hair
npm.cmd run assets:hair:review
```

第一个命令在 `workspace/cache/hair/first_bundle/` 生成或复用候选 Blend、manifest 和四视图，并执行组件/参数/骨骼合同验证。第二个命令生成四方向 Walk GIF。缓存可清理、可重建，不提交 Git；配方、脚本和验证器随 Git 保存。

当前候选状态为 `provisional`：整体位置与头骨动画已通过自动和网页检查，头顶中分处仍有一条小的头皮缝，等待用户人工审查。源头皮补片会形成巨大半球，平滑补片曾使 Blender 崩溃，两者均已拒绝且未进入正式流程；不得用网页遮挡物掩盖该问题。

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
