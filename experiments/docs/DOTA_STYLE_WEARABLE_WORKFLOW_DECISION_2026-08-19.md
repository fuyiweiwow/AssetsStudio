# Dota 式分类服装饰品工作流决策（2026-08-19）

## 1. 决策结论

AssetsLab 的短期目标改为建立 **Dota 式、Actor 类别固定、插槽和模板受控的服装饰品系统**，不再把“任意生成模型自动适配任意 Actor”作为当前里程碑。

核心单位不是“一件衣服适配所有人物”，而是：

`ActorClass + Slot + WearableArchetype + AssetCompiler + QA Gates`

- 一个 `ActorClass` 固定骨骼、静止姿势、体型包络、锚点和身体遮挡分区；
- 一个 `Slot` 规定可替换区域、允许骨骼、局部坐标和叠放顺序；
- 一个 `WearableArchetype` 规定该类饰品的拓扑模板、权重模板、接缝和活动余量；
- 每件新资产通过离线编译进入模板，而不是在运行时自动拟合；
- 只有通过静态、动作、穿插和四方向预览门禁的资产才能进入 Gallery、随机池或最终 3D→2D 渲染。

这允许“一类模型支持一类服装饰品”，同时把不可控的生成、拟合和蒙皮问题收敛为每个 Actor 类和每个饰品类别一次性的制作成本。

## 2. 当前判断

### 2.1 可以复用的基础

- 现有旧 Actor、既有骨骼和 walk 动画可以继续作为首个 `ActorClass`；Actor 与动作以后可以替换，不影响工作流合同。
- 现有 Cage、胸/肩/腰锚点和 torso slot control 已证明“饰品跟随同一骨骼动画”的技术合同可行。
- 当前 Hunyuan3D-2MV 夹克原始结果的多视图外观可以作为设计源；它不是可直接穿戴的生产网格。
- 项目的 4 方向 × 8 帧离线渲染和 3D→2D 输出合同继续保留。

### 2.2 已证伪或暂缓的路线

- 不再从 Actor 表面提取最终衣服；表面只可用于碰撞、距离和验收。
- 不再把 GarmentCode、全局 shrinkwrap、最近表面投影或统一缩放当作任意生成资产的自动适配器。
- 不再直接给 Hunyuan 高密度网格转移权重后期待其成为可用服装；这会同时放大体型、拓扑、领口、袖窿和穿插误差。
- 不把四个独立单视图模型拼成权威服装。
- 当前 loose jacket 属于高自由度软服装，保留为后续外观源，不作为第一项生产门禁。

## 3. 目标资产分级

按成功率从高到低推进：

1. **Tier A：刚性或近刚性挂件**。背部、肩部、胸甲、腰部附件；使用明确锚点或少量骨骼权重，允许制作隐藏身体 mask。
2. **Tier B：贴身蒙皮件**。上衣、手套、鞋、紧身裤；必须使用该 ActorClass 的干净模板拓扑和权重模板。
3. **Tier C：宽松软服装**。夹克、裙摆、披风；在 Tier B 稳定后增加分段权重、碰撞余量，必要时使用离线布料烘焙。
4. **Tier D：整套服装或跨体型自动适配**。只有前三层形成资产编译器和验收数据后再评估。

短期不追求 Tier C/D 的全自动化。

## 4. 每个 ActorClass 的一次性注册内容

首个类别暂定为 `ChibiActorV1`，注册包至少包含：

- canonical Actor 场景、骨骼名称映射、bind/rest pose 和单位/轴向；
- chest、back、shoulder、waist 等 slot 锚点与局部坐标；
- 身体包络和仅用于检测的 collision mesh；
- torso、upper-arm、pelvis 等可组合隐藏 mask；
- 各 Tier 的干净模板网格、允许骨骼白名单和权重模板；
- 固定的静态姿势、8 个 walk 样本和额外压力姿势；
- 统一的 front/right/back/left 相机和输出注册框。

新 Actor 不是重新发明整条管线，而是新增一个注册包。

## 5. 离线 Asset Compiler

一件生成或手工来源的饰品必须依次经过：

1. **Source Intake**：登记来源、许可、原始多视图/GLB、目标 ActorClass、Slot 和 Tier。
2. **Template Conform**：将外观重拓扑、投射或重建到该 archetype 的干净模板；保留设计特征，不保留生成网格的坏拓扑。
3. **Rig Compile**：复用模板权重或少量锚点，不对高密度源网格做无约束最近邻蒙皮。
4. **Coverage Compile**：生成显式身体隐藏 mask；隐藏被覆盖身体，而不是只靠把衣服推远避免穿模。
5. **Material Compile**：将源外观烘焙到模板 UV/材质。
6. **QA Compile**：输出几何、骨骼、权重、静态穿插、动作穿插和四方向预览报告。
7. **Render Package**：通过后才进入 4 方向 × 8 帧的 3D→2D 和最终像素清理。

Hunyuan3D-2MV 在该流程中的定位是 **Source Intake 的设计/高模生成器**，不是自动得到 game-ready wearable 的工具。

## 6. 硬性验收门禁

- 资产的 `ActorClass`、`Slot` 和 `WearableArchetype` 明确；
- 网格拓扑和面数适合后续烘焙与维护；
- 只包含允许的骨骼权重，权重归一且无游离顶点；
- body hide mask 能消除被覆盖区域的内部身体；
- 静止姿势无领口进入头部、严重悬浮或明显整体比例错误；
- front/right/back/left 均无不可接受的轮廓断裂；
- 8 个 walk 样本和压力姿势无严重穿插、塌陷或错误跟随；
- headless 预览和报告可复现；
- 未通过者只保留诊断记录，不进入 Gallery、随机池和运行时资源。

## 7. 下一项隔离实验

先建立 `ChibiActorV1 / torso_rigid / TorsoRigidAccessoryV1`，验证一类 Actor 对一类近刚性胸肩饰品的稳定穿戴：

1. 冻结现有旧 Actor、骨骼、bind pose、walk 和四方向相机；
2. 建立覆盖 chest/upper-back、避开领口和腋下的低自由度干净模板；
3. 模板只允许 spine/chest/shoulder 的受控权重，并提供显式 torso hide mask；
4. 先用简单可视化材质通过静止、四方向和 8 帧动作门禁；
5. 再把一个 Hunyuan 外观源烘焙/重建到同一模板，证明“换外观不换合同”；
6. 通过后再推进 `TorsoCloseFitV1`，最后才回到当前 loose jacket。

该实验优先验证插槽、模板、权重、遮挡和资产编译器，不同时解决软布料模拟。

## 8. 资源保留原则

清理本地实验时只保留：canonical Actor/骨骼/动作、slot/cage 控制资产、Hunyuan3D-2MV 模型与运行环境、已确认正确的多视图输入和原始 2MV GLB、下一实验所需脚本，以及一份失败结论记录。失败的绑定 v1-v8、单视图拼接结果、旋转诊断副本和可重建 review 缓存均不再作为资产保留。

删除本地失败结果不改变其结论：当前 2MV 夹克已经证明“源外观可用”，同时也证明“直接缩放/投影/转权重”不是生产绑定流程。
