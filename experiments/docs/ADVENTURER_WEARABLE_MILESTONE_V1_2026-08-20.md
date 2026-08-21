# 冒险者服饰工作流里程碑 V1（2026-08-20）

本里程碑完成 `ChibiActorV1 / AdventurerSetV1` 的七槽位穿戴验证。目标是保存“原型设计图 -> Hunyuan3D-2mv 生成源 -> Actor 类适配 -> 受控骨骼绑定 -> 动作审计 -> 四方向预览”的工作流，而不是把当前盔甲外观写死成唯一产物。

## 已完成范围

- 槽位：`head_hair`、`torso_outer`、`waist_accessory`、`legs_outer`、`feet_outer`、`wrist_accessory`、`back_accessory`。
- 可见部件均保留对应 Hunyuan3D-2mv 生成源；脚本几何只负责 Actor 边界过渡、遮挡、定位和绑定辅助。
- 袖子肩部不再使用固定抬升值，中心线由当前 Actor 的上臂和前臂骨骼推导；衣袖终端使用服装材质过渡环，手部顶点不进入遮挡掩码。
- 靴子、护腕和背包已经加入完整动作 Blend；七槽位最终审计均为 `pass`。
- 最终验收覆盖 front/right/back/left 以及动作帧 1、11、21、31、41、51、61、71。

## 更换 Actor 时能保证什么

这是一套可复用的 Actor 类资产编译方法，不是“任意服装一键适配任意 Actor”。新 Actor 可以沿用同一套步骤，但必须先建立自己的 Actor Profile。

- 静态穿戴至少需要干净的人体表面。
- 动画穿戴需要骨骼、蒙皮权重、稳定 bind/rest pose，并能映射骨盆、腰、脊柱、头、上肢、手、腿和脚语义骨骼。
- 骨骼命名不同可以通过别名或显式映射解决；缺失必要语义时只能进入 `static_only`，不能伪装成动画通过。
- 头身比例变化后，头发和贴身衣物必须根据新 Actor 的四视图重新生成，不能复用旧 Actor 的隔离图。
- 每个 Actor 类都要重跑槽位适配、遮挡和八帧动作门禁；通过后，同类服饰才能复用该类合同。

## 当前发布边界

发布包位于 `experiments/generated_wearables/`：

- `stage9_hunyuan_adapter_transfer_v1/` 保存 torso 编译器基础合同。
- `stage10_adventurer_set_v1/` 保存七槽位生成源、适配脚本、Actor Profile、审计报告、预览和最终 Blend。
- `MILESTONE_MANIFEST_V1.json` 保存最终 Blend 和七个生成源的 SHA-256。

失败头发、旧绑定候选和中间 Blend 不进入发布包、Gallery 或运行时随机池。完整复用步骤与强制门禁见 `stage10_adventurer_set_v1/WORKFLOW_REUSE_V1.md`。

## 下一阶段

下一项实验不应再重新制作一套盔甲，而应验证可替换性：优先使用同一 `ChibiActorV1` 合同制作第二套不同外观的 `torso_outer` 或 `wrist_accessory`；随后再选一个新 Actor，运行 Profile 提取与语义骨骼映射，只重做 Actor 相关的四视图、适配参数、遮挡和绑定，以确认工作流跨 Actor 类复现。
