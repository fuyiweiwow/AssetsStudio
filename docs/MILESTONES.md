# AssetsStudio 正式里程碑

本文件是所有资产状态的唯一人工入口。详细参数以各里程碑目录中的 `manifest.json` 和本目录对应工作流为准。

| 类别 | 当前版本 | 状态 | 结论 |
| --- | --- | --- | --- |
| 身体与动作 | `milestones/body/chibi_actor_mixamo_walk_v1.blend` | `accepted` | Actor V1，AccuRIG 骨架，Mixamo Walk 已绑定；Run 源保留 |
| 发型 | `milestones/hair/hair_component_catalog_v1.json` + `hair_random_pool_v1.json` + `first_bundle_recipe_v1.json` | `source_contract` | Chloe/Colin 组件化源、base 必选规则和离线随机池；首套女性 `seed_04_bangs04_v2` 已修复中心发片落入头皮的问题并通过投影覆盖验证，仍为 `provisional` 待人工审查 |
| 五官 | `milestones/body/face_contract_v2.json` + `chibi_actor_eye_assembly_v2.blend` | `technical_baseline` | EyeAssembly 浅曲面与3D耳朵随 `CC_Base_Head`；open/half/closed 确定性眨眼已恢复，等待用户审查后再晋级 |
| 短袖旧基线 | `milestones/tops/garmentcode_short_sleeve_v1/` | `provisional` | 保留作 GarmentCode 视觉回归参考；不再作为新服装生成主路线 |
| 服装生成路线筛选 | `docs/workflows/garment_workflow_candidates.md` + `docs/workflows/garment_workflow_screening_v1.md` | `in_progress` | DressCode/GarmentCode 保留为实验后端；正在筛选 Seamly2D + Blender Cloth、Blender 原生版片缝合、免费基础网格拟合三条可负担路线 |
| 短裤 | `milestones/pants/native_control_v0/` | `provisional` | Blender-native Actor 表面派生方案；用户视觉评价优于旧 GarmentCode 转移，自动严格门仍会误报/报警 |
| 鞋 | `milestones/shoes/cartoon_sneaker_v10/` | `accepted` | 用户确认可作为里程碑；加长鞋头/鞋跟、1.8 倍径向包络、Foot/ToeBase 刚性分区 |

## 不能再混淆的边界

1. 新服装主路线由 DressCode 生成版型和材质候选，再经过 AssetsStudio 的参数合同、Actor 适配和人工审查。
2. 当前短裤正式方向是 Blender-native 表面派生，不是旧 `solution2`、v31 或后续参数补丁。
3. F006 短袖最终网格仍来自 GarmentCode 静态仿真，但只作为旧基线；新服装不得默认复用其生成合同。
4. 鞋 v10 是当前唯一正式鞋里程碑；v1-v9 都不进入本仓库。
5. 自动审查只能发现异常，不能覆盖人工审查结论。

## 下一开发阶段

下一阶段先完成三条候选路线的最小斗篷筛选，统一检查静态碰撞、16 帧 Walk、三个形状参数和 GLB/FBX 导出；若没有取得授权明确且可下载的基础网格，则建立 Actor-native 长袍模板作为保底主线，再把魔法师长袍 recipe 接入 Studio 的生成预览与候选注册。Blender 继续负责权威适配、几何检查和最终 GIF/像素渲染。
