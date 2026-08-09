# AssetsStudio 正式里程碑

本文件是所有资产状态的唯一人工入口。详细参数以各里程碑目录中的 `manifest.json` 和本目录对应工作流为准。

| 类别 | 当前版本 | 状态 | 结论 |
| --- | --- | --- | --- |
| 身体与动作 | `milestones/body/chibi_actor_mixamo_walk_v1.blend` | `accepted` | Actor V1，AccuRIG 骨架，Mixamo Walk 已绑定；Run 源保留 |
| 发型 | `milestones/hair/hair_component_catalog_v1.json` + `hair_random_pool_v1.json` | `source_contract` | Chloe/Colin 组件化源、base 必选规则和离线随机池 |
| 五官 | `milestones/body/face_contract_v1.json` + Actor V1 内嵌对象 | `technical_baseline` | 眼睛、眉眼关系和3D耳朵随 `CC_Base_Head` 保留；旧2D/里程碑渲染测试已删除，3渲2能力由当前工具链验证 |
| 短袖 | `milestones/tops/actor_native_tshirt_v5/` | `provisional` | Actor 自身拓扑派生的单网格短袖；整体可用，但右肩/右袖突出仍是已知缺陷 |
| 短裤 | `milestones/pants/native_control_v0/` | `provisional` | Blender-native Actor 表面派生方案；用户视觉评价优于旧 GarmentCode 转移，自动严格门仍会误报/报警 |
| 鞋 | `milestones/shoes/cartoon_sneaker_v10/` | `accepted` | 用户确认可作为里程碑；加长鞋头/鞋跟、1.8 倍径向包络、Foot/ToeBase 刚性分区 |

## 不能再混淆的边界

1. GarmentCode 官方 demo 能生成有效纸样和模拟结果，但旧 Actor 体型转移没有形成可接受裤子或短袖基线。
2. 当前短裤正式方向是 Blender-native 表面派生，不是旧 `solution2`、v31 或后续参数补丁。
3. 当前短袖来自 Actor 表面单网格，不是 Colin 外部衣服，也不是 GarmentCode 生成结果。
4. 鞋 v10 是当前唯一正式鞋里程碑；v1-v9 都不进入本仓库。
5. 自动审查只能发现异常，不能覆盖人工审查结论。

## 下一开发阶段

先把当前资产合同包装成 Studio 的配方数据与前端预览接口，再考虑 Three.js 节点/蓝图编辑器。Blender 继续负责权威几何生成和最终 GIF/像素渲染。
